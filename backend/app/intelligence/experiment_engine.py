"""
Experiment engine — runs systematic experiments on the environment.
Only active in TRAIN mode. In DEMO mode, users can view but not start experiments.
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select
from ..memory.models import Experiment, ExperimentRun
from ..memory.database import get_db

logger = logging.getLogger(__name__)

class ExperimentEngine:
    def __init__(self, app_state, device_manager=None):
        self.app_state = app_state
        self.device_manager = device_manager

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def create_experiment(
        self,
        name: str,
        description: str,
        variable: str,
        values_to_test: list,
        outcome_metric: str,
        runs_per_value: int = 3,
    ) -> dict:
        """Create a new experiment. Only starts it in TRAIN mode."""
        async with get_db() as db:
            exp = Experiment(
                name=name,
                description=description,
                variable=variable,
                values_to_test=values_to_test,
                outcome_metric=outcome_metric,
                runs_per_value=runs_per_value,
                status="pending" if not self._is_active_mode() else "pending",
            )
            db.add(exp)
            await db.commit()
            await db.refresh(exp)
            return {"id": exp.id, "name": exp.name, "status": exp.status}

    async def start_experiment(self, experiment_id: int) -> bool:
        """Start an experiment. Requires TRAIN mode."""
        if not self._is_active_mode():
            return False

        async with get_db() as db:
            result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
            exp = result.scalar_one_or_none()
            if not exp or exp.status not in ("pending", "paused"):
                return False

            exp.status = "running"
            exp.started_at = datetime.utcnow()
            await db.commit()

        logger.info(f"Started experiment: {exp.name}")
        return True

    async def record_run_outcome(self, experiment_id: int, value_tested, outcome_value: float, outcome_data: dict = None):
        """Record the outcome of one experimental run."""
        if not self._is_active_mode():
            return

        async with get_db() as db:
            run = ExperimentRun(
                experiment_id=experiment_id,
                value_tested=value_tested,
                run_date=datetime.utcnow(),
                outcome_value=outcome_value,
                outcome_data=outcome_data or {},
            )
            db.add(run)
            await db.commit()

        # Check if experiment is complete
        await self._check_completion(experiment_id)

    async def _check_completion(self, experiment_id: int):
        async with get_db() as db:
            result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
            exp = result.scalar_one_or_none()
            if not exp or exp.status != "running":
                return

            runs_result = await db.execute(
                select(ExperimentRun).where(ExperimentRun.experiment_id == experiment_id)
            )
            runs = runs_result.scalars().all()

            total_needed = len(exp.values_to_test) * exp.runs_per_value
            if len(runs) >= total_needed:
                # Analyze results
                summary = self._analyze_results(exp.values_to_test, runs)
                exp.results_summary = summary
                exp.optimal_value = summary.get("optimal_value")
                exp.status = "complete"
                exp.completed_at = datetime.utcnow()
                await db.commit()
                logger.info(f"Experiment '{exp.name}' completed. Optimal: {exp.optimal_value}")

    def _analyze_results(self, values_to_test: list, runs: list) -> dict:
        """Calculate which value produced the best outcomes."""
        from collections import defaultdict
        import statistics

        value_outcomes = defaultdict(list)
        for run in runs:
            if run.outcome_value is not None:
                key = str(run.value_tested)
                value_outcomes[key].append(run.outcome_value)

        results = {}
        for val in values_to_test:
            key = str(val)
            outcomes = value_outcomes.get(key, [])
            if outcomes:
                results[key] = {
                    "mean": statistics.mean(outcomes),
                    "stdev": statistics.stdev(outcomes) if len(outcomes) > 1 else 0,
                    "n": len(outcomes),
                }

        if not results:
            return {"results": results, "optimal_value": None}

        optimal = max(results.keys(), key=lambda k: results[k]["mean"])
        return {"results": results, "optimal_value": optimal}

    async def get_experiment(self, experiment_id: int) -> Optional[dict]:
        async with get_db() as db:
            result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
            exp = result.scalar_one_or_none()
            if not exp:
                return None

            runs_result = await db.execute(
                select(ExperimentRun).where(ExperimentRun.experiment_id == experiment_id)
                .order_by(ExperimentRun.run_date.desc())
            )
            runs = runs_result.scalars().all()

            return {
                "id": exp.id,
                "name": exp.name,
                "description": exp.description,
                "variable": exp.variable,
                "values_to_test": exp.values_to_test,
                "outcome_metric": exp.outcome_metric,
                "runs_per_value": exp.runs_per_value,
                "status": exp.status,
                "current_value_index": exp.current_value_index,
                "results_summary": exp.results_summary,
                "optimal_value": exp.optimal_value,
                "runs": [
                    {
                        "value_tested": r.value_tested,
                        "run_date": r.run_date.isoformat(),
                        "outcome_value": r.outcome_value,
                    }
                    for r in runs
                ],
            }

    async def list_experiments(self) -> list:
        async with get_db() as db:
            result = await db.execute(
                select(Experiment).order_by(Experiment.created_at.desc())
            )
            experiments = result.scalars().all()
            return [
                {
                    "id": e.id,
                    "name": e.name,
                    "variable": e.variable,
                    "outcome_metric": e.outcome_metric,
                    "status": e.status,
                    "results_summary": e.results_summary,
                    "optimal_value": e.optimal_value,
                    "demo_mode_blocked": not self._is_active_mode() and e.status == "pending",
                }
                for e in experiments
            ]

    async def pause_experiment(self, experiment_id: int):
        async with get_db() as db:
            result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
            exp = result.scalar_one_or_none()
            if exp and exp.status == "running":
                exp.status = "paused"
                await db.commit()
