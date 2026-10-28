"""PDF upload, management, and processing routes."""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, send_file, jsonify
)
from flask_login import login_required, current_user

from app import db, limiter
from app.models.pdf import PDF
from app.services import pdf_service
from app.services.ai_providers import get_embedding_provider
from app.services.vectorstore_service import VectorStoreService
from app.utils.validators import allowed_file
from app.utils.decorators import owns_pdf

pdf_bp = Blueprint("pdf", __name__, url_prefix="/pdfs")


def _vectorstore() -> VectorStoreService:
    return VectorStoreService(current_app.config["INDEX_FOLDER"], current_app.config["EMBEDDING_DIMENSIONS"])


@pdf_bp.route("/")
@login_required
def library():
    query = current_user.pdfs
    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(PDF.title.ilike(f"%{search}%"))

    status = request.args.get("status")
    if status:
        query = query.filter_by(processing_status=status)

    sort = request.args.get("sort", "newest")
    sort_map = {
        "newest": PDF.created_at.desc(),
        "oldest": PDF.created_at.asc(),
        "title": PDF.title.asc(),
        "size": PDF.file_size_bytes.desc(),
    }
    query = query.order_by(sort_map.get(sort, PDF.created_at.desc()))

    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=current_app.config["PDFS_PER_PAGE"], error_out=False)

    return render_template(
        "pdf/library.html",
        pdfs=pagination.items,
        pagination=pagination,
        search=search,
        sort=sort,
        status=status,
    )


@pdf_bp.route("/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per hour")
def upload():
    if request.method == "GET":
        return render_template("pdf/upload.html")

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Please choose a PDF file to upload.", "error")
        return redirect(url_for("pdf.upload"))

    if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        flash("Only PDF files are supported.", "error")
        return redirect(url_for("pdf.upload"))

    title = request.form.get("title", "").strip() or file.filename

    stored_filename, abs_path, size = pdf_service.save_uploaded_file(file, current_app.config["UPLOAD_FOLDER"])
    pdf = pdf_service.create_pdf_record(
        user_id=current_user.id,
        title=title,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=abs_path,
        size_bytes=size,
    )

    settings = current_user.settings
    try:
        pdf_service.process_pdf_pipeline(
            pdf,
            embedding_provider=get_embedding_provider(),
            vectorstore=_vectorstore(),
            chunk_size=settings.chunk_size if settings else current_app.config["DEFAULT_CHUNK_SIZE"],
            chunk_overlap=settings.chunk_overlap if settings else current_app.config["DEFAULT_CHUNK_OVERLAP"],
        )
        current_user.register_activity()
        db.session.commit()
        flash(f'"{pdf.title}" was uploaded and processed successfully.', "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Upload succeeded but processing failed: {e}", "error")

    return redirect(url_for("pdf.detail", pdf_id=pdf.id))


@pdf_bp.route("/<int:pdf_id>")
@login_required
@owns_pdf
def detail(pdf_id, pdf):
    return render_template("pdf/detail.html", pdf=pdf)


@pdf_bp.route("/<int:pdf_id>/reprocess", methods=["POST"])
@login_required
@owns_pdf
def reprocess(pdf_id, pdf):
    settings = current_user.settings
    try:
        pdf_service.process_pdf_pipeline(
            pdf,
            embedding_provider=get_embedding_provider(),
            vectorstore=_vectorstore(),
            chunk_size=settings.chunk_size if settings else current_app.config["DEFAULT_CHUNK_SIZE"],
            chunk_overlap=settings.chunk_overlap if settings else current_app.config["DEFAULT_CHUNK_OVERLAP"],
        )
        flash("Document reprocessed.", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Reprocessing failed: {e}", "error")
    return redirect(url_for("pdf.detail", pdf_id=pdf.id))


@pdf_bp.route("/<int:pdf_id>/rename", methods=["POST"])
@login_required
@owns_pdf
def rename(pdf_id, pdf):
    new_title = request.form.get("title", "").strip()
    if new_title:
        pdf.title = new_title
        db.session.commit()
        flash("Renamed successfully.", "success")
    return redirect(request.referrer or url_for("pdf.library"))


@pdf_bp.route("/<int:pdf_id>/favorite", methods=["POST"])
@login_required
@owns_pdf
def toggle_favorite(pdf_id, pdf):
    pdf.is_favorite = not pdf.is_favorite
    db.session.commit()
    return jsonify({"success": True, "is_favorite": pdf.is_favorite})


@pdf_bp.route("/<int:pdf_id>/delete", methods=["POST"])
@login_required
@owns_pdf
def delete(pdf_id, pdf):
    title = pdf.title
    pdf_service.delete_pdf(pdf, _vectorstore())
    flash(f'"{title}" was deleted.', "info")
    return redirect(url_for("pdf.library"))


@pdf_bp.route("/<int:pdf_id>/download")
@login_required
@owns_pdf
def download(pdf_id, pdf):
    return send_file(pdf.file_path, as_attachment=True, download_name=pdf.original_filename)
