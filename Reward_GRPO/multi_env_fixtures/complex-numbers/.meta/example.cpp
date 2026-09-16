#include <algorithm>
#include <cmath>
#include <limits>

#include "complex_numbers.h"

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
    Complex prod{re * other.re - im * other.im, im * other.re + re * other.im};
    return prod;
}

Complex Complex::operator/(const Complex& other) const {
    // Scale both operands by exact powers of two before multiplying. Squaring
    // finite double components directly can overflow or underflow even when the
    // quotient is representable (for example, (1e200 + 2e200i)/(3e200 + 4e200i)).
    int numerator_exponent = 0;
    int denominator_exponent = 0;
    std::frexp(std::max(std::abs(re), std::abs(im)), &numerator_exponent);
    std::frexp(std::max(std::abs(other.re), std::abs(other.im)),
               &denominator_exponent);
    const double a = std::scalbn(re, -numerator_exponent);
    const double b = std::scalbn(im, -numerator_exponent);
    const double c = std::scalbn(other.re, -denominator_exponent);
    const double d = std::scalbn(other.im, -denominator_exponent);
    const double denominator = c * c + d * d;
    const int exponent = numerator_exponent - denominator_exponent;
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
