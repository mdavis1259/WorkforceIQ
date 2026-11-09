import numpy as np
from sklearn.linear_model import LinearRegression

class ForecastService:

    def generate_forecast():
        # Sample historical demand data
        days = np.array([1, 2, 3, 4, 5]).reshape(-1, 1)

        demand = np.array([100, 120, 140, 160, 180])

        model = LinearRegression()
        model.fit(days, demand)
        prediction = model.predict([[6]])

        return round(prediction[0])   

