from flask import Blueprint, render_template

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')

@dashboard_bp.route('/', methods=['GET'])
def dashboard():
    """Render the main SDK dashboard"""
    return render_template('dashboard.html')

@dashboard_bp.route('/Campaigns', methods=['GET'])
def campaigns():
    """Render the campaigns management page"""
    return render_template('campaigns.html')

@dashboard_bp.route('/Audience', methods=['GET'])
def audience():
    """Render the audience overview page"""
    return render_template('audience.html')

@dashboard_bp.route('/Settings', methods=['GET'])
def settings():
    """Render the settings page"""
    return render_template('settings.html')
