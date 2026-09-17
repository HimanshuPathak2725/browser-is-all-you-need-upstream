#include <algorithm>
#include <cmath>
#include <limits>

#include "complex_numbers.h"

namespace {
// Normalize finite components without squaring their original magnitude.
int normalize(double& real, double& imaginary) {
    int exponent = 0;
    std::frexp(std::max(std::abs(real), std::abs(imaginary)), &exponent);
    real = std::scalbn(real, -exponent);
    imaginary = std::scalbn(imaginary, -exponent);
    return exponent;
}
}  // namespace

namespace complex_numbers {

Complex::Complex(double r, double i) : re(r), im(i) {}

Complex Complex::operator+(const Complex& other) const {
    Complex sum{re + other.re, im + other.im};
    return sum;
}

Complex Complex::operator-(const Complex& other) const {
    Complex diff{re - other.re, im - other.im};
    return diff;
}

Complex Complex::operator*(const Complex& other) const {
    double a = re, b = im, c = other.re, d = other.im;
    const int exponent = normalize(a, b) + normalize(c, d);
    return Complex{std::scalbn(a * c - b * d, exponent),
                   std::scalbn(b * c + a * d, exponent)};
}

Complex Complex::operator/(const Complex& other) const {
    double a = re, b = im, c = other.re, d = other.im;
    const int exponent = normalize(a, b) - normalize(c, d);
    const double denominator = c * c + d * d;
    return Complex{std::scalbn((a * c + b * d) / denominator, exponent),
                   std::scalbn((b * c - a * d) / denominator, exponent)};
}

double Complex::abs() const { return std::hypot(re, im); }

Complex Complex::conj() const {
    Complex cx{re, -im};
    return cx;
}

double Complex::real() const { return re; }

double Complex::imag() const { return im; }

Complex Complex::exp() const {
    if (re > std::log(std::numeric_limits<double>::max())) {
        // Each component can remain finite even when the magnitude overflows.
        const double half_scale = std::exp(re / 2);
        return Complex{(half_scale * std::cos(im)) * half_scale,
                       (half_scale * std::sin(im)) * half_scale};
    }
    Complex ex{std::exp(re) * std::cos(im), std::exp(re) * std::sin(im)};
    return ex;
}

bool operator==(const Complex& lhs, const Complex& rhs) {
    return lhs.real() == rhs.real() && lhs.imag() == rhs.imag();
}

std::ostream& operator<<(std::ostream& os, Complex const& value) {
    os << "(" << value.real() << "," << value.imag() << ")";
    return os;
}

Complex operator+(const Complex& complex, double scalar) {
    Complex sum{complex.real() + scalar, complex.imag()};
    return sum;
}

Complex operator+(double scalar, const Complex& complex) {
    Complex sum{complex.real() + scalar, complex.imag()};
    return sum;
}

Complex operator-(const Complex& complex, double scalar) {
    Complex diff{complex.real() - scalar, complex.imag()};
    return diff;
}

Complex operator-(double scalar, const Complex& complex) {
    Complex diff{scalar - complex.real(), 0 - complex.imag()};
    return diff;
}

Complex operator*(const Complex& complex, double scalar) {
    Complex prod{complex.real() * scalar, complex.imag() * scalar};
    return prod;
}

Complex operator*(double scalar, const Complex& complex) {
    Complex prod{complex.real() * scalar, complex.imag() * scalar};
    return prod;
}

Complex operator/(const Complex& complex, double scalar) {
    Complex other{scalar, 0};
    return complex / other;
}

Complex operator/(double scalar, const Complex& complex) {
    Complex other{scalar, 0};
    return other / complex;
}

}  // namespace complex_numbers
