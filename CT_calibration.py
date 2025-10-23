
import numpy as np
import matplotlib.pyplot as plt

# Given data points
x = np.array([85, 2370, 78, 1660])
y = np.array([0.215, 6.26, 0.178, 4.32])

# Fit a 2nd-degree polynomial (quadratic)
coeffs = np.polyfit(x, y, 2)
print("Polynomial coefficients (a*x^2 + b*x + c):", coeffs)

# Create a polynomial function from coefficients
poly = np.poly1d(coeffs)

def get_current(adc_value):
    return poly(adc_value)

if __name__ == "__main__":
    # Generate x values for smooth curve
    x_fit = np.linspace(min(x)-50, max(x)+50, 500)
    y_fit = poly(x_fit)

    # Plot data points
    plt.scatter(x, y, color='red', label='Data Points')

    # Plot fitted polynomial
    plt.plot(x_fit, y_fit, color='blue', label='Best Fit Quadratic')

    plt.xlabel('x')
    plt.ylabel('y')
    plt.title('2nd Degree Polynomial Fit')
    plt.legend()
    plt.grid(True)
    plt.show()
