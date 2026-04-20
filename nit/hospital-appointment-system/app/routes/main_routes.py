# ============================================================
# Main Routes - Landing Page & Static Pages
# ============================================================

from flask import Blueprint, render_template, redirect, url_for

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def landing():
    """Starting/Landing page with Curonix branding."""
    return render_template('landing.html')


@main_bp.route('/home')
def index():
    """Deprecated home page route redirected to login."""
    return redirect(url_for('auth.login_page'))


@main_bp.route('/about')
def about():
    """About page."""
    return render_template('about.html')
