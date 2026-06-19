from flask import Blueprint, render_template

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')

@dashboard_bp.route('/', methods=['GET'])
def dashboard():
    """Render the main SDK dashboard"""
    return render_template('dashboard.html')
