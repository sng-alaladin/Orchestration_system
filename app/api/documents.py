"""문서 API — 기획/참고 문서 업로드, 생성 산출물(PRD/Backlog) 조회·다운로드."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.core.enums import DocumentKind, DocumentType
from app.db.models.project import Project
from app.db.models.project_document import ProjectDocument
from app.db.session import get_db

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])

_MAX_UPLOAD_BYTES = 1 * 1024 * 1024  # 1MB (MVP: 텍스트 기획 문서)
_ALLOWED_UPLOAD_TYPES = {DocumentType.IDEA, DocumentType.REFERENCE}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    kind: str
    doc_type: str
    filename: str
    content_type: str

    @classmethod
    def from_model(cls, doc: ProjectDocument) -> "DocumentResponse":
        return cls(
            id=doc.id,
            kind=doc.kind,
            doc_type=doc.doc_type,
            filename=doc.filename,
            content_type=doc.content_type,
        )


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile,
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
    doc_type: DocumentType = DocumentType.REFERENCE,
) -> DocumentResponse:
    if doc_type not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "업로드할 수 있는 문서 유형이 아닙니다."
        )
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "문서가 너무 큽니다. 1MB 이하의 텍스트 문서를 올려 주세요.",
        )
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "텍스트 문서(UTF-8)만 지원합니다. 문서를 텍스트로 저장해 다시 올려 주세요.",
        ) from exc

    document = ProjectDocument(
        project_id=project.id,
        user_id=project.user_id,
        kind=DocumentKind.UPLOADED,
        doc_type=doc_type,
        filename=file.filename or "document.txt",
        content_type=file.content_type or "text/plain",
        content=content,
    )
    db.add(document)
    await db.commit()
    return DocumentResponse.from_model(document)


@router.get("")
async def list_documents(
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentResponse]:
    stmt = (
        select(ProjectDocument)
        .where(ProjectDocument.project_id == project.id)
        .order_by(ProjectDocument.created_at)
    )
    documents = (await db.execute(stmt)).scalars().all()
    return [DocumentResponse.from_model(d) for d in documents]


@router.get("/{document_id}")
async def download_document(
    document_id: uuid.UUID,
    project: Annotated[Project, Depends(get_owned_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlainTextResponse:
    stmt = select(ProjectDocument).where(
        ProjectDocument.id == document_id, ProjectDocument.project_id == project.id
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "문서를 찾을 수 없습니다.")
    return PlainTextResponse(
        document.content,
        media_type=document.content_type,
        headers={"Content-Disposition": f'attachment; filename="{document.filename}"'},
    )
