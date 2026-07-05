from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import require_lawyer_or_admin
from app.db.session import get_db
from app.models.user import User
from app.services.export_service import act_references_csv, saved_items_csv, saved_items_markdown

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/saved-items.csv")
def export_saved_items_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lawyer_or_admin),
) -> Response:
    return Response(
        saved_items_csv(db, current_user),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=saved-items.csv"},
    )


@router.get("/saved-items.md")
def export_saved_items_markdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lawyer_or_admin),
) -> Response:
    return Response(
        saved_items_markdown(db, current_user),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=saved-items.md"},
    )


@router.get("/act/{act_id}/references.csv")
def export_act_references_csv(
    act_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_lawyer_or_admin),
) -> Response:
    return Response(
        act_references_csv(db, act_id),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=act-references.csv"},
    )
