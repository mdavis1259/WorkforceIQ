from availability.AvailabilityRepository import getUserAvailability
from availability.AvailabilityService import formatAvailabilityData
from flask import Blueprint, render_template
from flask_login import current_user

avail = Blueprint('availability', __name__, template_folder='templates')

@avail.route('/availability')
def availability():
    return render_template('availability.html')
    # return render_template('availability.html', availability=formatAvailabilityData(getUserAvailability(current_user.userid)))