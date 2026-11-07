from flask import Flask, render_template, request
from flask_login import LoginManager, login_required, current_user

from database.connection import get_db_connection

from employee_management.EmployeeRoutes import employee_bp
from authentication.AuthRoutes import auth_bp
from forecasting.ForecastingRoutes import forecast_bp
from ai_assistant.AssistantRoutes import assistant_bp

from user_management.User import User
from user_management.UserService import UserService
from user_management.UserRepository import UserRepository

from forecasting.ForecastService import ForecastService
from ai_assistant.AssistantService import AssistantService


app = Flask(__name__)
app.config["DATABASE"] = "database/workforce.db"
app.register_blueprint(auth_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(forecast_bp)
app.register_blueprint(assistant_bp)
app.secret_key = (
    app.config.get("SECRET_KEY")
    or "development-key-change-in-production"
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

# =====================================================
# LOGIN MANAGER
# =====================================================
@login_manager.user_loader
def load_user(user_id):

    conn = get_db_connection()

    try:
        user_repository = UserRepository(conn)
        user_service = UserService(user_repository)

        return user_service.get_user_by_id(user_id)

    finally:
        conn.close()

# =======================================================
# DASHBOARD ROUTES
# =======================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """ Displays the WorkforceIQ manager dashboard """
    return render_template("dashboard.html", level = current_user.system_role_id)


if __name__ == "__main__":
    app.run(debug=True)
    
