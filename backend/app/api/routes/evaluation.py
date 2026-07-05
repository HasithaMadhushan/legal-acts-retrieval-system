from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.evaluation import EvaluationGoldReference, EvaluationRun
from app.models.user import User
from app.schemas.evaluation import (
    EvaluationMetricsSummary,
    EvaluationRunCreate,
    EvaluationRunRead,
    GoldReferenceCreate,
    GoldReferenceRead,
)
from app.services.evaluation_service import metrics_summary, run_reference_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"], dependencies=[Depends(require_admin)])


@router.get("/gold-references", response_model=list[GoldReferenceRead])
def list_gold_references(db: Session = Depends(get_db)) -> list[EvaluationGoldReference]:
    return (
        db.query(EvaluationGoldReference)
        .order_by(EvaluationGoldReference.created_at.desc())
        .all()
    )


@router.post("/gold-references", response_model=GoldReferenceRead, status_code=201)
def create_gold_reference(
    payload: GoldReferenceCreate,
    db: Session = Depends(get_db),
) -> EvaluationGoldReference:
    gold = EvaluationGoldReference(**payload.model_dump())
    db.add(gold)
    db.commit()
    db.refresh(gold)
    return gold


@router.get("/metrics-summary", response_model=EvaluationMetricsSummary)
def get_metrics_summary(db: Session = Depends(get_db)) -> dict:
    return metrics_summary(db)


@router.post("/run", response_model=EvaluationRunRead)
def run_evaluation(
    payload: EvaluationRunCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> EvaluationRun:
    return run_reference_evaluation(
        db,
        run_name=payload.run_name,
        act_id=payload.act_id,
        section_segmentation_accuracy=payload.section_segmentation_accuracy,
    )


@router.get("/runs", response_model=list[EvaluationRunRead])
def list_runs(db: Session = Depends(get_db)) -> list[EvaluationRun]:
    return db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).all()


@router.get("/runs/{run_id}", response_model=EvaluationRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> EvaluationRun | None:
    return db.get(EvaluationRun, run_id)
