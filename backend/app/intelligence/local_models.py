"""
Local model training using scikit-learn.
Trains simple models on user data for fast real-time predictions.
Only trains in ACTIVE mode.
"""
import logging
import json
import os
import pickle
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy import select
from ..memory.models import Observation, BiometricReading
from ..memory.database import get_db

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'models')

class LocalModelTrainer:
    def __init__(self, app_state):
        self.app_state = app_state
        os.makedirs(MODEL_DIR, exist_ok=True)

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def train_all(self):
        """Train all available models on accumulated data. Only in ACTIVE mode."""
        if not self._is_active_mode():
            logger.info("Skipping model training — not in ACTIVE mode")
            return

        logger.info("Starting local model training...")

        await self._train_stress_predictor()
        await self._train_sleep_time_predictor()

        logger.info("Local model training complete")

    async def _train_stress_predictor(self):
        """Train a model to predict stress from time/day features."""
        try:
            from sklearn.ensemble import RandomForestRegressor
        except ImportError:
            logger.warning("scikit-learn not installed — skipping local model training")
            return

        async with get_db() as db:
            result = await db.execute(
                select(BiometricReading).where(
                    BiometricReading.stress_level.isnot(None)
                ).order_by(BiometricReading.timestamp.desc()).limit(500)
            )
            readings = result.scalars().all()

        if len(readings) < 20:
            logger.info("Not enough biometric data for stress predictor (need 20+)")
            return

        X, y = [], []
        for r in readings:
            ts = r.timestamp
            X.append([
                ts.hour,
                ts.weekday(),
                int(ts.weekday() >= 5),  # is_weekend
                ts.hour / 24.0,           # normalized hour
            ])
            y.append(r.stress_level)

        model = RandomForestRegressor(n_estimators=50, random_state=42)
        model.fit(X, y)

        model_path = os.path.join(MODEL_DIR, 'stress_predictor.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

        logger.info(f"Stress predictor trained on {len(readings)} samples, saved to {model_path}")

    async def _train_sleep_time_predictor(self):
        """Train a model to predict when the user goes to sleep."""
        try:
            from sklearn.tree import DecisionTreeClassifier
        except ImportError:
            return

        async with get_db() as db:
            result = await db.execute(
                select(Observation).where(
                    Observation.obs_type == "biometric",
                    Observation.subject.like("%sleep%"),
                ).limit(200)
            )
            obs = result.scalars().all()

        if len(obs) < 10:
            return

        X, y = [], []
        for o in obs:
            ts = o.timestamp
            X.append([ts.hour, ts.weekday(), int(ts.weekday() >= 5)])
            y.append(1 if ts.hour < 6 or ts.hour >= 22 else 0)

        model = DecisionTreeClassifier(max_depth=4, random_state=42)
        model.fit(X, y)

        model_path = os.path.join(MODEL_DIR, 'sleep_predictor.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

        logger.info(f"Sleep predictor trained on {len(obs)} samples")

    def predict_stress(self, hour: int, day_of_week: int) -> Tuple[Optional[float], float]:
        """Predict stress level. Returns (prediction, confidence) or (None, 0)."""
        model_path = os.path.join(MODEL_DIR, 'stress_predictor.pkl')
        if not os.path.exists(model_path):
            return None, 0.0

        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)

            X = [[hour, day_of_week, int(day_of_week >= 5), hour / 24.0]]
            prediction = model.predict(X)[0]

            # Estimate confidence from tree variance
            if hasattr(model, 'estimators_'):
                preds = [e.predict(X)[0] for e in model.estimators_]
                import statistics
                std = statistics.stdev(preds) if len(preds) > 1 else 10
                confidence = max(0.0, min(1.0, 1.0 - std / 50))
            else:
                confidence = 0.5

            return prediction, confidence
        except Exception as e:
            logger.debug(f"Prediction failed: {e}")
            return None, 0.0

    async def get_model_status(self) -> dict:
        models = {}
        for name in ['stress_predictor', 'sleep_predictor']:
            path = os.path.join(MODEL_DIR, f'{name}.pkl')
            models[name] = {
                "trained": os.path.exists(path),
                "last_modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
                    if os.path.exists(path) else None,
            }
        return models
