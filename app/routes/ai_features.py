"""Routes for all the generative study tools (summaries, flashcards, quizzes...)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from app.models.flashcard import FlashcardSet, Flashcard
from app.models.quiz import Quiz, QuizQuestion
from app.services import ai_generation_service as ai_gen
from app.services.ai_providers import get_ai_provider
from app.utils.decorators import json_errors, owns_pdf

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")


@ai_bp.route("/pdf/<int:pdf_id>/summary")
@login_required
@owns_pdf
def summary(pdf_id, pdf):
    style = request.args.get("style", "detailed")
    text = ai_gen.generate_summary(pdf_id, get_ai_provider(), style=style)
    current_user.register_activity()
    db.session.commit()
    return render_template("pdf/summary.html", pdf=pdf, summary_text=text, style=style)


@ai_bp.route("/pdf/<int:pdf_id>/flashcards", methods=["GET", "POST"])
@login_required
@owns_pdf
def flashcards(pdf_id, pdf):
    existing_sets = pdf.flashcard_sets.order_by(FlashcardSet.created_at.desc()).all()

    if request.method == "POST":
        count = request.form.get("count", 12, type=int)
        cards_data = ai_gen.generate_flashcards(pdf_id, get_ai_provider(), count=count)
        if not cards_data:
            flash("Could not generate flashcards. Please try again.", "error")
            return redirect(url_for("ai.flashcards", pdf_id=pdf_id))

        fc_set = FlashcardSet(user_id=current_user.id, pdf_id=pdf_id, title=f"{pdf.title} — Flashcards")
        db.session.add(fc_set)
        db.session.flush()
        for c in cards_data:
            db.session.add(Flashcard(
                set_id=fc_set.id,
                front=c.get("front", ""),
                back=c.get("back", ""),
                difficulty=c.get("difficulty", "medium"),
            ))
        current_user.register_activity()
        db.session.commit()
        return redirect(url_for("ai.view_flashcard_set", set_id=fc_set.id))

    return render_template("pdf/flashcards_home.html", pdf=pdf, existing_sets=existing_sets)


@ai_bp.route("/flashcards/<int:set_id>")
@login_required
def view_flashcard_set(set_id):
    fc_set = FlashcardSet.query.get_or_404(set_id)
    if fc_set.user_id != current_user.id:
        from flask import abort
        abort(403)
    cards = fc_set.cards.all()
    return render_template("pdf/flashcards_view.html", fc_set=fc_set, cards=cards)


@ai_bp.route("/pdf/<int:pdf_id>/quiz", methods=["GET", "POST"])
@login_required
@owns_pdf
def quiz(pdf_id, pdf):
    existing_quizzes = pdf.quizzes.order_by(Quiz.created_at.desc()).all()

    if request.method == "POST":
        quiz_type = request.form.get("quiz_type", "mcq")
        count = request.form.get("count", 10, type=int)
        difficulty = request.form.get("difficulty", "medium")

        questions_data = ai_gen.generate_quiz(pdf_id, get_ai_provider(), quiz_type=quiz_type,
                                               count=count, difficulty=difficulty)
        if not questions_data:
            flash("Could not generate a quiz. Please try again.", "error")
            return redirect(url_for("ai.quiz", pdf_id=pdf_id))

        quiz_obj = Quiz(user_id=current_user.id, pdf_id=pdf_id, title=f"{pdf.title} — Quiz",
                         quiz_type=quiz_type, difficulty=difficulty)
        db.session.add(quiz_obj)
        db.session.flush()
        for q in questions_data:
            question = QuizQuestion(
                quiz_id=quiz_obj.id,
                question_type=q.get("type", quiz_type),
                question_text=q.get("question", ""),
                correct_answer=q.get("correct_answer", ""),
                explanation=q.get("explanation", ""),
            )
            question.options = q.get("options", [])
            db.session.add(question)
        current_user.register_activity()
        db.session.commit()
        return redirect(url_for("ai.take_quiz", quiz_id=quiz_obj.id))

    return render_template("pdf/quiz_home.html", pdf=pdf, existing_quizzes=existing_quizzes)


@ai_bp.route("/quiz/<int:quiz_id>")
@login_required
def take_quiz(quiz_id):
    quiz_obj = Quiz.query.get_or_404(quiz_id)
    if quiz_obj.user_id != current_user.id:
        from flask import abort
        abort(403)
    questions = quiz_obj.questions.all()
    return render_template("pdf/quiz_take.html", quiz=quiz_obj, questions=questions)


@ai_bp.route("/quiz/<int:quiz_id>/grade", methods=["POST"])
@login_required
@json_errors
def grade_quiz(quiz_id):
    quiz_obj = Quiz.query.get_or_404(quiz_id)
    if quiz_obj.user_id != current_user.id:
        from flask import abort
        abort(403)
    answers = (request.get_json(silent=True) or {}).get("answers", {})  # {question_id: answer}

    results, correct_count = [], 0
    for q in quiz_obj.questions.all():
        given = answers.get(str(q.id), "")
        is_correct = given.strip().lower() == (q.correct_answer or "").strip().lower()
        correct_count += int(is_correct)
        results.append({
            "question_id": q.id, "correct": is_correct,
            "correct_answer": q.correct_answer, "explanation": q.explanation,
        })

    total = quiz_obj.questions.count()
    return jsonify({
        "success": True, "score": correct_count, "total": total,
        "percentage": round((correct_count / total) * 100, 1) if total else 0,
        "results": results,
    })


@ai_bp.route("/pdf/<int:pdf_id>/notes")
@login_required
@owns_pdf
def study_notes(pdf_id, pdf):
    notes = ai_gen.generate_study_notes(pdf_id, get_ai_provider())
    current_user.register_activity()
    db.session.commit()
    return render_template("pdf/study_notes.html", pdf=pdf, notes=notes)


@ai_bp.route("/pdf/<int:pdf_id>/mindmap")
@login_required
@owns_pdf
def mind_map(pdf_id, pdf):
    tree = ai_gen.generate_mind_map_outline(pdf_id, get_ai_provider())
    return render_template("pdf/mindmap.html", pdf=pdf, tree=tree)


@ai_bp.route("/pdf/<int:pdf_id>/eli10", methods=["GET", "POST"])
@login_required
@owns_pdf
def eli10(pdf_id, pdf):
    explanation = None
    topic = ""
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        if topic:
            explanation = ai_gen.explain_like_im_10(pdf_id, get_ai_provider(), topic)
    return render_template("pdf/eli10.html", pdf=pdf, explanation=explanation, topic=topic)


@ai_bp.route("/pdf/<int:pdf_id>/important-questions")
@login_required
@owns_pdf
def important_questions(pdf_id, pdf):
    content = ai_gen.generate_important_questions(pdf_id, get_ai_provider())
    return render_template("pdf/generated_text.html", pdf=pdf, title="Important Questions", content=content)


@ai_bp.route("/pdf/<int:pdf_id>/interview-questions")
@login_required
@owns_pdf
def interview_questions(pdf_id, pdf):
    content = ai_gen.generate_interview_questions(pdf_id, get_ai_provider())
    return render_template("pdf/generated_text.html", pdf=pdf, title="Interview Questions", content=content)


@ai_bp.route("/pdf/<int:pdf_id>/learning-objectives")
@login_required
@owns_pdf
def learning_objectives(pdf_id, pdf):
    content = ai_gen.generate_learning_objectives(pdf_id, get_ai_provider())
    return render_template("pdf/generated_text.html", pdf=pdf, title="Learning Objectives", content=content)


@ai_bp.route("/pdf/<int:pdf_id>/difficulty")
@login_required
@owns_pdf
@json_errors
def difficulty_analysis(pdf_id, pdf):
    data = ai_gen.analyze_difficulty(pdf_id, get_ai_provider())
    return jsonify({"success": True, "data": data})


@ai_bp.route("/pdf/<int:pdf_id>/topics")
@login_required
@owns_pdf
@json_errors
def topics_keywords(pdf_id, pdf):
    data = ai_gen.extract_topics_and_keywords(pdf_id, get_ai_provider())
    pdf.topics = ", ".join(data.get("topics", []))
    pdf.keywords = ", ".join(data.get("keywords", []))
    db.session.commit()
    return jsonify({"success": True, "data": data})
