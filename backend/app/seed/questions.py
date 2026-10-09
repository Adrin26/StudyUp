"""SPM-style sample questions.

Maths/Science topics use parametric generators (deterministic via the seeded
RNG); language/humanities topics are hand-written. These are illustrative
samples — replace them with licensed past-year papers for production.
"""

import random
from fractions import Fraction

SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def sup(n: int) -> str:
    return str(n).translate(SUP)


def num(n) -> str:
    """Display a number with a proper minus sign."""
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return str(n).replace("-", "−")


def frac(a: int, b: int) -> str:
    f = Fraction(a, b)
    return num(f.numerator) if f.denominator == 1 else f"{num(f.numerator)}/{f.denominator}"


def signed(n: int, var: str = "") -> str:
    """' + 5x' / ' − 5x' for non-leading terms; omits 1 coefficients on variables."""
    if n == 0:
        return ""
    coef = "" if abs(n) == 1 and var else str(abs(n))
    return f" {'+' if n > 0 else '−'} {coef}{var}"


def lead(n: int, var: str) -> str:
    if n == 1:
        return var
    if n == -1:
        return f"−{var}"
    return f"{num(n)}{var}"


def quad(a: int, b: int, c: int) -> str:
    return f"{lead(a, 'x²')}{signed(b, 'x')}{signed(c)}"


def mcq(text, correct, distractors, explanation, skill, difficulty="medium", fillers=None):
    opts = [str(correct)]
    for d in list(distractors) + list(fillers or []):
        d = str(d)
        if d not in opts:
            opts.append(d)
        if len(opts) == 4:
            break
    assert len(opts) == 4, f"Not enough distinct options for: {text}"
    return {"type": "mcq", "text": text, "options": opts, "correct": str(correct), "explanation": explanation, "skill": skill, "difficulty": difficulty}


def short(text, answer, explanation, skill, difficulty="medium", accept=()):
    return {"type": "short_answer", "text": text, "correct": "|".join([str(answer), *map(str, accept)]), "explanation": explanation, "skill": skill, "difficulty": difficulty}


def nz(rng, lo, hi):
    while True:
        v = rng.randint(lo, hi)
        if v != 0:
            return v


# ---------------------------------------------------------------- Mathematics

def q_quad_solve(rng):
    m, n = rng.sample([v for v in range(-6, 7) if v != 0], 2)
    m, n = sorted((m, n))
    eq = quad(1, -(m + n), m * n)
    correct = f"x = {num(m)} or x = {num(n)}"
    d = [f"x = {num(-n)} or x = {num(-m)}", f"x = {num(m)} or x = {num(-n)}", f"x = {num(-m)} or x = {num(n)}", f"x = {num(m + n)} or x = {num(m * n)}"]
    exp = f"Find two numbers that multiply to {num(m * n)} and add to {num(-(m + n))}: {num(-m)} and {num(-n)}. So (x{signed(-m)})(x{signed(-n)}) = 0, giving x = {num(m)} or x = {num(n)}."
    diff = "easy" if m > 0 and n > 0 else "medium"
    return mcq(f"Solve {eq} = 0.", correct, d, exp, "Solving equations", diff, [f"x = {num(m - 1)} or x = {num(n + 1)}"])


def q_quad_factorise(rng):
    m, n = rng.sample([v for v in range(-7, 8) if v != 0], 2)
    expr = quad(1, m + n, m * n)
    correct = f"(x{signed(m)})(x{signed(n)})"
    d = [f"(x{signed(-m)})(x{signed(-n)})", f"(x{signed(m)})(x{signed(-n)})", f"(x{signed(-m)})(x{signed(n)})"]
    exp = f"We need two numbers with product {num(m * n)} and sum {num(m + n)}: {num(m)} and {num(n)}. So {expr} = {correct}."
    return mcq(f"Factorise completely: {expr}", correct, d, exp, "Factorisation", "easy" if m > 0 and n > 0 else "medium", [f"(x{signed(m * n)})(x{signed(1)})"])


def q_quad_general(rng):
    p, q = nz(rng, -6, 6), nz(rng, -6, 6)
    correct = f"{quad(1, p + q, p * q)} = 0"
    d = [f"{quad(1, p * q, p + q)} = 0", f"{quad(1, -(p + q), p * q)} = 0", f"{quad(1, p + q, -(p * q))} = 0"]
    exp = f"Expand: (x{signed(p)})(x{signed(q)}) = x² + {num(p)}x + {num(q)}x + {num(p * q)} = {quad(1, p + q, p * q)}."
    return mcq(f"Express (x{signed(p)})(x{signed(q)}) = 0 in the general form ax² + bx + c = 0.", correct, d, exp, "Standard form", "easy", [f"{quad(2, p + q, p * q)} = 0"])


def q_quad_identify(rng):
    a, b, c = rng.randint(2, 6), nz(rng, -9, 9), nz(rng, -9, 9)
    eq = f"{quad(a, b, c)} = 0"
    which = rng.choice(["a", "b", "c"])
    val = {"a": a, "b": b, "c": c}[which]
    others = [num(-val), num(a), num(b), num(c), num(val + 1)]
    exp = f"Compare {eq} with ax² + bx + c = 0: a = {num(a)}, b = {num(b)}, c = {num(c)}. Remember to include the sign."
    return mcq(f"For the quadratic equation {eq}, what is the value of {which}?", num(val), [o for o in others if o != num(val)], exp, "Standard form", "easy")


def q_quad_nature(rng):
    kind = rng.choice(["distinct", "equal", "none"])
    a = rng.randint(1, 3)
    if kind == "equal":
        r = nz(rng, -4, 4)
        b, c = -2 * a * r, a * r * r
    else:
        while True:
            b, c = nz(rng, -8, 8), nz(rng, -8, 8)
            disc = b * b - 4 * a * c
            if (kind == "distinct" and disc > 0) or (kind == "none" and disc < 0):
                break
    disc = b * b - 4 * a * c
    answers = {"distinct": "Two real and distinct roots", "equal": "Two equal real roots", "none": "No real roots"}
    exp = f"b² − 4ac = ({num(b)})² − 4({a})({num(c)}) = {num(disc)}. " + {"distinct": "Since it is > 0, there are two distinct real roots.", "equal": "Since it equals 0, the roots are equal.", "none": "Since it is < 0, there are no real roots."}[kind]
    return mcq(f"Determine the type of roots of {quad(a, b, c)} = 0.", answers[kind], [v for k, v in answers.items() if k != kind], exp, "Roots & discriminant", "hard", ["Infinitely many roots"])


def q_quad_positive_root(rng):
    m, n = rng.randint(1, 9), -rng.randint(1, 9)
    eq = quad(1, -(m + n), m * n)
    exp = f"Factorise: (x{signed(-m)})(x{signed(-n)}) = 0, so x = {m} or x = {num(n)}. The positive root is {m}."
    return short(f"Find the positive root of {eq} = 0.", m, exp, "Solving equations", "hard")


def q_lin_solve(rng):
    a, x, b = rng.randint(2, 9), rng.randint(-5, 12), nz(rng, -20, 20)
    c = a * x + b
    exp = f"{'Subtract' if b > 0 else 'Add'} {abs(b)} on both sides: {a}x = {num(c - b)}. Divide by {a}: x = {num(x)}."
    return mcq(f"Solve {a}x{signed(b)} = {num(c)}.", f"x = {num(x)}", [f"x = {num(-x)}", f"x = {num(x + 1)}", f"x = {frac(c + b, a)}"], exp, "Solving linear equations", "easy", [f"x = {num(x - 2)}"])


def q_lin_brackets(rng):
    a, b, x = rng.randint(2, 6), nz(rng, -6, 6), rng.randint(-4, 9)
    c = a * (x + b)
    exp = f"Divide both sides by {a}: x{signed(b)} = {num(c // a)}. Then x = {num(x)}."
    return short(f"Solve {a}(x{signed(b)}) = {num(c)}.", x, exp, "Solving linear equations", "medium")


def q_lin_simultaneous(rng):
    x, y = rng.randint(-3, 9), rng.randint(-3, 9)
    s, d = x + y, x - y
    exp = f"Add the equations: 2x = {num(s + d)}, so x = {num(x)}. Substitute: y = {num(s)} − {num(x)} = {num(y)}."
    return mcq(f"Solve the simultaneous equations: x + y = {num(s)} and x − y = {num(d)}.", f"x = {num(x)}, y = {num(y)}", [f"x = {num(y)}, y = {num(x)}", f"x = {num(-x)}, y = {num(-y)}", f"x = {num(s)}, y = {num(d)}"], exp, "Simultaneous equations", "medium", [f"x = {num(x + 1)}, y = {num(y - 1)}"])


def q_lin_simultaneous_hard(rng):
    x, y = rng.randint(1, 8), rng.randint(-4, 6)
    a, b = rng.randint(2, 4), rng.randint(2, 4)
    e1, e2 = a * x + y, x + b * y
    exp = f"From the first equation, y = {num(e1)} − {a}x. Substitute into the second: x + {b}({num(e1)} − {a}x) = {num(e2)}, giving x = {x}."
    return short(f"Given {a}x + y = {num(e1)} and x + {b}y = {num(e2)}, find the value of x.", x, exp, "Simultaneous equations", "hard")


def q_lin_word(rng):
    k, n, add = rng.randint(2, 6), rng.randint(3, 15), rng.randint(1, 20)
    total = k * n + add
    exp = f"Let the number be n: {k}n + {add} = {total}, so {k}n = {total - add} and n = {n}."
    return short(f"{['Twice', 'Three times', 'Four times', 'Five times', 'Six times'][k - 2]} a number plus {add} equals {total}. Find the number.", n, exp, "Forming equations", "medium")


def q_fn_eval(rng):
    a, b, k = nz(rng, -5, 6), nz(rng, -9, 9), rng.randint(-4, 6)
    v = a * k + b
    f = f"{lead(a, 'x')}{signed(b)}"
    exp = f"Substitute x = {num(k)}: f({num(k)}) = {num(a)}({num(k)}){signed(b)} = {num(v)}."
    return mcq(f"Given f(x) = {f}, find f({num(k)}).", num(v), [num(a * k - b), num(a + k + b), num(-v)], exp, "Function notation", "easy", [num(v + a)])


def q_fn_inverse_value(rng):
    a, b, x = rng.randint(2, 6), nz(rng, -9, 9), rng.randint(-3, 8)
    k = a * x + b
    exp = f"f⁻¹({num(k)}) is the x such that f(x) = {num(k)}: {a}x{signed(b)} = {num(k)}, so x = {num(x)}."
    return short(f"Given f(x) = {a}x{signed(b)}, find f⁻¹({num(k)}).", x, exp, "Inverse functions", "medium")


def q_fn_inverse_expr(rng):
    a, b = rng.randint(2, 7), nz(rng, -9, 9)
    correct = f"(x{signed(-b)})/{a}"
    exp = f"Let y = {a}x{signed(b)}. Then x = (y{signed(-b)})/{a}. Swap: f⁻¹(x) = {correct}."
    return mcq(f"Given f(x) = {a}x{signed(b)}, find f⁻¹(x).", correct, [f"(x{signed(b)})/{a}", f"{a}x{signed(-b)}", f"(x{signed(-a)})/{num(b)}"], exp, "Inverse functions", "hard")


def q_fn_composite(rng):
    a, b, c, d = rng.randint(2, 4), nz(rng, -5, 5), rng.randint(2, 4), nz(rng, -5, 5)
    k = rng.randint(-2, 4)
    g = c * k + d
    fg = a * g + b
    exp = f"First g({num(k)}) = {c}({num(k)}){signed(d)} = {num(g)}. Then f({num(g)}) = {a}({num(g)}){signed(b)} = {num(fg)}."
    gf = c * (a * k + b) + d
    return mcq(f"Given f(x) = {a}x{signed(b)} and g(x) = {c}x{signed(d)}, find fg({num(k)}).", num(fg), [num(gf), num(g), num(fg + a)], exp, "Composite functions", "hard", [num(fg - 1)])


def q_fn_find_k(rng):
    a, b, k = rng.randint(2, 7), nz(rng, -9, 9), rng.randint(-4, 9)
    v = a * k + b
    exp = f"{a}k{signed(b)} = {num(v)} → {a}k = {num(v - b)} → k = {num(k)}."
    return short(f"Given f(x) = {a}x{signed(b)} and f(k) = {num(v)}, find the value of k.", k, exp, "Function notation", "medium")


TRIPLES = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25)]


def q_trig_ratio(rng):
    o, a, h = rng.choice(TRIPLES)
    if rng.random() < 0.5:
        o, a = a, o
    k = rng.randint(1, 3)
    o, a, h = o * k, a * k, h * k
    ratio = rng.choice(["sin", "cos", "tan"])
    vals = {"sin": frac(o, h), "cos": frac(a, h), "tan": frac(o, a)}
    exp = {"sin": "sin θ = opposite / hypotenuse", "cos": "cos θ = adjacent / hypotenuse", "tan": "tan θ = opposite / adjacent"}[ratio] + f" = {vals[ratio]}."
    d = [v for r, v in vals.items() if r != ratio] + [frac(h, o)]
    return mcq(f"In a right-angled triangle, the side opposite angle θ is {o} cm, the adjacent side is {a} cm and the hypotenuse is {h} cm. Find {ratio} θ.", vals[ratio], d, exp, "Trigonometric ratios", "easy" if k == 1 else "medium")


def q_trig_pythag(rng):
    o, a, h = rng.choice(TRIPLES)
    k = rng.randint(1, 3)
    exp = f"By Pythagoras: hypotenuse² = {o * k}² + {a * k}² = {(h * k) ** 2}, so hypotenuse = {h * k} cm."
    return short(f"A right-angled triangle has shorter sides {o * k} cm and {a * k} cm. Find the length of the hypotenuse in cm.", h * k, exp, "Pythagoras' theorem", "easy")


def q_trig_side(rng):
    o, a, h = rng.choice(TRIPLES)
    k = rng.randint(2, 5)
    exp = f"sin θ = opposite / hypotenuse → opposite = {h * k} × {o}/{h} = {o * k} cm."
    return short(f"Given sin θ = {o}/{h} and the hypotenuse is {h * k} cm, find the length of the side opposite θ in cm.", o * k, exp, "Trigonometric ratios", "medium")


def q_trig_special(rng):
    items = [("sin 30°", "0.5", ["0.866", "1", "0"]), ("cos 60°", "0.5", ["0.866", "0", "1"]), ("tan 45°", "1", ["0.5", "0", "1.732"]), ("cos 0°", "1", ["0", "0.5", "−1"]), ("sin 90°", "1", ["0", "0.5", "0.707"])]
    q, c, d = rng.choice(items)
    return mcq(f"What is the value of {q}?", c, d, f"{q} = {c}. Memorise the special angle values.", "Special angles", "easy")


def _data(rng, n):
    return [rng.randint(1, 20) for _ in range(n)]


def q_stat_mean(rng):
    n = rng.choice([4, 5, 6])
    while True:
        data = _data(rng, n)
        if sum(data) % n == 0:
            break
    m = sum(data) // n
    exp = f"Sum = {sum(data)}. Mean = {sum(data)} ÷ {n} = {m}."
    return mcq(f"Find the mean of: {', '.join(map(str, data))}", m, [sorted(data)[n // 2], max(data) - min(data), m + 1], exp, "Mean", "easy", [m - 1, m + 2])


def q_stat_median(rng):
    n = rng.choice([5, 6, 7])
    data = _data(rng, n)
    s = sorted(data)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    exp = f"Arrange in order: {', '.join(map(str, s))}. " + ("The middle value is " if n % 2 else "Mean of the two middle values = ") + f"{num(med)}."
    return short(f"Find the median of: {', '.join(map(str, data))}", num(med), exp, "Median", "medium" if n % 2 else "hard")


def q_stat_mode(rng):
    base = rng.sample(range(1, 15), 4)
    mode = base[0]
    data = base + [mode, mode]
    rng.shuffle(data)
    return mcq(f"Find the mode of: {', '.join(map(str, data))}", mode, [b for b in base[1:]], f"{mode} appears most often (3 times).", "Mode", "easy")


def q_stat_range(rng):
    data = _data(rng, 6)
    r = max(data) - min(data)
    return mcq(f"Find the range of: {', '.join(map(str, data))}", r, [max(data), r + 1, num(round(sum(data) / 6, 1))], f"Range = {max(data)} − {min(data)} = {r}.", "Range", "easy", [r - 1])


def q_stat_missing(rng):
    n = 4
    data = _data(rng, 3)
    m = rng.randint(max(data) // 2 + 3, 15)
    missing = m * n - sum(data)
    if missing <= 0:
        missing += n * 5
        m += 5
    exp = f"Total = mean × n = {m} × {n} = {m * n}. Missing value = {m * n} − {sum(data)} = {missing}."
    return short(f"The mean of four numbers is {m}. Three of the numbers are {', '.join(map(str, data))}. Find the fourth number.", missing, exp, "Mean", "hard")


def q_idx_multiply(rng):
    m, n = rng.randint(2, 9), rng.randint(2, 9)
    v = rng.choice("xyamp")
    return mcq(f"Simplify {v}{sup(m)} × {v}{sup(n)}.", f"{v}{sup(m + n)}", [f"{v}{sup(m * n)}", f"{v}{sup(abs(m - n) or 1)}", f"2{v}{sup(m + n)}"], f"Same base, multiply → add the indices: {m} + {n} = {m + n}.", "Laws of indices", "easy")


def q_idx_divide(rng):
    m, n = rng.randint(6, 12), rng.randint(2, 5)
    v = rng.choice("xyab")
    return mcq(f"Simplify {v}{sup(m)} ÷ {v}{sup(n)}.", f"{v}{sup(m - n)}", [f"{v}{sup(m + n)}", f"{v}{sup(m // n)}" if m // n != m - n else f"{v}{sup(m)}", f"{v}{sup(m * n)}"], f"Same base, divide → subtract the indices: {m} − {n} = {m - n}.", "Laws of indices", "easy")


def q_idx_power(rng):
    m, n = rng.randint(2, 6), rng.randint(2, 5)
    v = rng.choice("xyk")
    return mcq(f"Simplify ({v}{sup(m)}){sup(n)}.", f"{v}{sup(m * n)}", [f"{v}{sup(m + n)}", f"{n}{v}{sup(m)}", f"{v}{sup(m ** n)}" if m ** n != m * n else f"{v}{sup(m)}"], f"Power of a power → multiply the indices: {m} × {n} = {m * n}.", "Laws of indices", "medium")


def q_idx_eval(rng):
    b, e = rng.choice([(2, rng.randint(3, 8)), (3, rng.randint(2, 5)), (5, rng.randint(2, 4))])
    return short(f"Evaluate {b}{sup(e)}.", b ** e, f"{b}{sup(e)} = {' × '.join([str(b)] * e)} = {b ** e}.", "Evaluating powers", "easy")


def q_idx_coefficient(rng):
    c, m, n = rng.randint(2, 5), rng.randint(2, 4), rng.choice([2, 3])
    return mcq(f"Simplify ({c}x{sup(m)}){sup(n)}.", f"{c ** n}x{sup(m * n)}", [f"{c}x{sup(m * n)}", f"{c * n}x{sup(m * n)}", f"{c ** n}x{sup(m + n)}"], f"Raise both parts: {c}{sup(n)} = {c ** n} and (x{sup(m)}){sup(n)} = x{sup(m * n)}.", "Laws of indices", "hard")


def q_idx_negative(rng):
    b, e = rng.choice([(2, 2), (2, 3), (3, 2), (4, 2), (5, 2), (10, 2)])
    return mcq(f"Evaluate {b}{sup(-e)}.", f"1/{b ** e}", [f"−{b ** e}", f"{b ** e}", f"−1/{b ** e}"], f"A negative index means reciprocal: {b}{sup(-e)} = 1/{b}{sup(e)} = 1/{b ** e}.", "Negative & zero indices", "hard")


# ------------------------------------------------------- Additional Mathematics

def q_diff_power(rng):
    a, n = rng.randint(2, 9), rng.randint(2, 6)
    correct = f"{a * n}x{sup(n - 1) if n - 1 > 1 else ''}"
    return mcq(f"Differentiate y = {a}x{sup(n)} with respect to x.", correct, [f"{a}x{sup(n - 1) if n > 2 else ''}", f"{a * n}x{sup(n)}", f"{a + n}x{sup(n - 1) if n > 2 else ''}"], f"Power rule: multiply by {n} and reduce the power by 1 → {correct}.", "Power rule", "easy")


def q_diff_poly(rng):
    a, b, c = rng.randint(2, 6), nz(rng, -9, 9), nz(rng, -9, 9)
    correct = f"{3 * a}x²{signed(2 * b, 'x')}"
    exp = f"Differentiate each term: {a}x³ → {3 * a}x², {num(b)}x² → {num(2 * b)}x, constant {num(c)} → 0."
    return mcq(f"Find dy/dx for y = {a}x³{signed(b, 'x²')}{signed(c)}.", correct, [f"{3 * a}x²{signed(2 * b, 'x')}{signed(c)}", f"{a}x²{signed(b, 'x')}", f"{3 * a}x³{signed(2 * b, 'x²')}"], exp, "Power rule", "medium")


def q_diff_gradient(rng):
    a, b, k = rng.randint(1, 5), nz(rng, -8, 8), rng.randint(-3, 4)
    g = 2 * a * k + b
    exp = f"dy/dx = {2 * a}x{signed(b)}. At x = {num(k)}: {2 * a}({num(k)}){signed(b)} = {num(g)}."
    return short(f"Find the gradient of the curve y = {lead(a, 'x²')}{signed(b, 'x')} at x = {num(k)}.", g, exp, "Gradient of a curve", "medium")


def q_diff_find_x(rng):
    b, x = nz(rng, -8, 8), rng.randint(-4, 6)
    v = 2 * x + b
    exp = f"dy/dx = 2x{signed(b)}. Set 2x{signed(b)} = {num(v)} → x = {num(x)}."
    return short(f"The gradient of y = x²{signed(b, 'x')} is {num(v)} at a point. Find the x-coordinate of that point.", x, exp, "Gradient of a curve", "hard")


def q_ap_nth(rng):
    a, d, n = rng.randint(-5, 10), nz(rng, -4, 6), rng.randint(6, 20)
    t = a + (n - 1) * d
    seq = ", ".join(num(a + i * d) for i in range(3))
    exp = f"a = {num(a)}, d = {num(d)}. Tₙ = a + (n − 1)d = {num(a)} + ({n} − 1)({num(d)}) = {num(t)}."
    return short(f"Find the {n}th term of the arithmetic progression {seq}, …", t, exp, "nth term", "easy" if d > 0 else "medium")


def q_ap_diff(rng):
    a, d = rng.randint(-10, 15), nz(rng, -7, 9)
    seq = ", ".join(num(a + i * d) for i in range(4))
    return mcq(f"What is the common difference of {seq}, …?", num(d), [num(-d), num(a), num(d * 2)], f"d = second term − first term = {num(a + d)} − {num(a)} = {num(d)}.", "Common difference", "easy", [num(d + 1)])


def q_ap_sum(rng):
    a, d, n = rng.randint(1, 10), rng.randint(1, 6), rng.randint(5, 15)
    s = n * (2 * a + (n - 1) * d) // 2
    exp = f"Sₙ = n/2 [2a + (n − 1)d] = {n}/2 [2({a}) + {n - 1}({d})] = {s}."
    return short(f"Find the sum of the first {n} terms of the AP {a}, {a + d}, {a + 2 * d}, …", s, exp, "Sum of terms", "hard")


def q_ap_which(rng):
    a, d, n = rng.randint(1, 9), rng.randint(2, 7), rng.randint(8, 25)
    v = a + (n - 1) * d
    exp = f"{a} + (n − 1)({d}) = {v} → n − 1 = {(v - a) // d} → n = {n}."
    return short(f"Which term of the AP {a}, {a + d}, {a + 2 * d}, … is equal to {v}?", n, exp, "nth term", "medium")


# ------------------------------------------------------------------- Physics

def q_el_ohm(rng):
    i, r = rng.randint(1, 6), rng.choice([2, 3, 4, 5, 6, 8, 10, 12])
    v = i * r
    which = rng.choice(["V", "I", "R"])
    if which == "V":
        return mcq(f"A current of {i} A flows through a {r} Ω resistor. What is the potential difference across it?", f"{v} V", [f"{frac(r, i)} V", f"{i + r} V", f"{frac(i, r)} V"], f"V = IR = {i} × {r} = {v} V.", "Ohm's law", "easy", [f"{v * 2} V"])
    if which == "I":
        return short(f"A {v} V supply is connected across a {r} Ω resistor. Find the current in A.", i, f"I = V/R = {v}/{r} = {i} A.", "Ohm's law", "easy")
    return short(f"A current of {i} A flows when {v} V is applied across a resistor. Find its resistance in Ω.", r, f"R = V/I = {v}/{i} = {r} Ω.", "Ohm's law", "medium")


def q_el_power(rng):
    v, i = rng.choice([3, 6, 12, 24, 240]), rng.choice([0.5, 1, 2, 3, 5])
    p = v * i
    return mcq(f"A device operates at {v} V and draws {num(float(i))} A. What is its power?", f"{num(float(p))} W", [f"{num(round(v / i, 2))} W", f"{num(float(v + i))} W", f"{num(float(p * 2))} W"], f"P = VI = {v} × {num(float(i))} = {num(float(p))} W.", "Electrical power", "easy")


def q_el_series(rng):
    rs = rng.sample([2, 3, 4, 5, 6, 8, 10], rng.choice([2, 3]))
    return short(f"Resistors of {', '.join(f'{r} Ω' for r in rs)} are connected in series. Find the effective resistance in Ω.", sum(rs), f"In series, add them: {' + '.join(map(str, rs))} = {sum(rs)} Ω.", "Series & parallel", "easy")


def q_el_parallel(rng):
    r = rng.choice([4, 6, 8, 10, 12, 20])
    return mcq(f"Two identical {r} Ω resistors are connected in parallel. What is the effective resistance?", f"{num(r / 2)} Ω", [f"{2 * r} Ω", f"{r} Ω", f"{num(r / 4)} Ω"], f"1/R = 1/{r} + 1/{r} = 2/{r}, so R = {num(r / 2)} Ω.", "Series & parallel", "medium")


def q_el_charge(rng):
    i, t = rng.randint(2, 8), rng.choice([5, 10, 20, 30, 60])
    return short(f"A current of {i} A flows for {t} s. Calculate the charge that flows, in C.", i * t, f"Q = It = {i} × {t} = {i * t} C.", "Charge & current", "medium")


def q_el_combo(rng):
    r1, r = rng.choice([2, 3, 4, 5]), rng.choice([4, 6, 8, 12])
    total = r1 + r / 2
    v = rng.choice([6, 12, 24])
    i = round(v / total, 2)
    return short(f"A {r1} Ω resistor is in series with two {r} Ω resistors connected in parallel. A {v} V supply is used. Find the current from the supply in A (2 d.p.).", num(i), f"Parallel part = {num(r / 2)} Ω. Total = {r1} + {num(r / 2)} = {num(total)} Ω. I = {v}/{num(total)} = {num(i)} A.", "Series & parallel", "hard")


def q_fm_velocity(rng):
    u, a, t = rng.randint(0, 10), rng.randint(1, 5), rng.randint(2, 10)
    v = u + a * t
    return mcq(f"A car starts with velocity {u} m s⁻¹ and accelerates uniformly at {a} m s⁻² for {t} s. What is its final velocity?", f"{v} m s⁻¹", [f"{a * t} m s⁻¹", f"{u + a + t} m s⁻¹", f"{u * a * t} m s⁻¹" if u * a * t != v else f"{v + 2} m s⁻¹"], f"v = u + at = {u} + {a}({t}) = {v} m s⁻¹.", "Equations of motion", "easy" if u == 0 else "medium", [f"{v - 1} m s⁻¹"])


def q_fm_accel(rng):
    u, a, t = rng.randint(0, 10), rng.randint(1, 6), rng.randint(2, 8)
    v = u + a * t
    return short(f"An object's velocity changes from {u} m s⁻¹ to {v} m s⁻¹ in {t} s. Find its acceleration in m s⁻².", a, f"a = (v − u)/t = ({v} − {u})/{t} = {a} m s⁻².", "Equations of motion", "medium")


def q_fm_force(rng):
    m, a = rng.choice([0.5, 1, 2, 3, 5, 10, 1200]), rng.randint(1, 6)
    f = m * a
    return mcq(f"A net force acts on a {num(float(m))} kg object, giving it an acceleration of {a} m s⁻². What is the net force?", f"{num(float(f))} N", [f"{num(round(m / a, 2))} N", f"{num(float(m + a))} N", f"{num(float(f * 2))} N"], f"F = ma = {num(float(m))} × {a} = {num(float(f))} N.", "Newton's second law", "easy")


def q_fm_find_accel(rng):
    m, a = rng.choice([2, 4, 5, 8, 10]), rng.randint(1, 6)
    f = m * a
    return short(f"A force of {f} N acts on a {m} kg trolley on a frictionless surface. Find its acceleration in m s⁻².", a, f"a = F/m = {f}/{m} = {a} m s⁻².", "Newton's second law", "medium")


def q_fm_momentum(rng):
    m, v = rng.choice([0.2, 0.5, 2, 4, 60, 1000]), rng.randint(2, 25)
    p = m * v
    return mcq(f"What is the momentum of a {num(float(m))} kg object moving at {v} m s⁻¹?", f"{num(float(p))} kg m s⁻¹", [f"{num(round(m / v, 3))} kg m s⁻¹", f"{num(float(m + v))} kg m s⁻¹", f"{num(float(p / 2))} kg m s⁻¹"], f"p = mv = {num(float(m))} × {v} = {num(float(p))} kg m s⁻¹.", "Momentum", "medium")


def q_fm_weight(rng):
    m = rng.choice([2, 5, 10, 50, 60])
    w = round(m * 9.81, 2)
    return short(f"Calculate the weight, in N, of a {m} kg mass on Earth. (g = 9.81 m s⁻²)", num(w), f"W = mg = {m} × 9.81 = {num(w)} N.", "Weight & gravity", "hard")


# ----------------------------------------------------------------- Chemistry

COMPOUNDS = [("H₂O", "H = 1, O = 16", 18), ("CO₂", "C = 12, O = 16", 44), ("NaOH", "Na = 23, O = 16, H = 1", 40), ("CaCO₃", "Ca = 40, C = 12, O = 16", 100), ("MgO", "Mg = 24, O = 16", 40), ("NH₃", "N = 14, H = 1", 17), ("CH₄", "C = 12, H = 1", 16)]


def q_mole_moles(rng):
    f, ram, mm = rng.choice(COMPOUNDS)
    n = rng.choice([0.5, 1, 2, 3, 4])
    mass = mm * n
    return mcq(f"How many moles are in {num(float(mass))} g of {f}? [Relative atomic mass: {ram}]", f"{num(float(n))} mol", [f"{num(float(n * 2))} mol", f"{num(round(mm / mass, 2))} mol", f"{num(float(mass))} mol"], f"Molar mass of {f} = {mm} g mol⁻¹. n = {num(float(mass))} ÷ {mm} = {num(float(n))} mol.", "Mass and moles", "easy" if n >= 1 else "medium", [f"{num(float(n + 1))} mol"])


def q_mole_mass(rng):
    f, ram, mm = rng.choice(COMPOUNDS)
    n = rng.choice([0.25, 0.5, 2, 3, 5])
    return short(f"Calculate the mass, in g, of {num(float(n))} mol of {f}. [Relative atomic mass: {ram}]", num(float(mm * n)), f"Mass = n × molar mass = {num(float(n))} × {mm} = {num(float(mm * n))} g.", "Mass and moles", "medium")


def q_mole_particles(rng):
    n = rng.choice([0.5, 2, 3, 5])
    correct = f"{num(round(n * 6.02, 2))} × 10²³"
    return mcq(f"How many molecules are in {num(float(n))} mol of oxygen gas? [Avogadro constant = 6.02 × 10²³ mol⁻¹]", correct, [f"{num(round(6.02 / n, 2))} × 10²³", f"{num(round(n * 6.02 * 2, 2))} × 10²³", f"{num(float(n))} × 10²³"], f"Number of particles = n × Nₐ = {num(float(n))} × 6.02 × 10²³ = {correct}.", "Number of particles", "medium")


def q_mole_molar_mass(rng):
    f, ram, mm = rng.choice(COMPOUNDS)
    return mcq(f"What is the relative molecular/formula mass of {f}? [Relative atomic mass: {ram}]", mm, [mm + 2, mm - 1, mm * 2], f"Add up the relative atomic masses in {f} to get {mm}.", "Molar mass", "easy")


# --------------------------------------------------------- Hand-written sets

def H(text, correct, distractors, explanation, skill, difficulty="medium"):
    return mcq(text, correct, distractors, explanation, skill, difficulty)


BONDING = [
    H("Which type of bond is formed when electrons are transferred from one atom to another?", "Ionic bond", ["Covalent bond", "Metallic bond", "Hydrogen bond"], "Transfer of electrons from a metal to a non-metal forms ions held by an ionic bond.", "Ionic bonds", "easy"),
    H("Which compound is formed by covalent bonding?", "CO₂", ["NaCl", "MgO", "KBr"], "Carbon and oxygen are both non-metals, so they share electrons.", "Covalent bonds", "easy"),
    H("A sodium atom (2.8.1) forms a sodium ion. What is the charge of the ion?", "+1", ["−1", "+2", "0"], "Sodium loses its one valence electron to achieve an octet, forming Na⁺.", "Ionic bonds", "easy"),
    H("How many pairs of electrons are shared in a molecule of oxygen, O₂?", "2", ["1", "3", "4"], "Each oxygen atom needs 2 more electrons, so they share 2 pairs, forming a double bond.", "Covalent bonds", "medium"),
    H("Why do ionic compounds conduct electricity when molten?", "Their ions are free to move", ["Their electrons are delocalised in the solid", "They contain shared electron pairs", "Their molecules are small"], "In the molten state, the ions are no longer fixed in a lattice and can move to carry charge.", "Properties of compounds", "medium"),
    H("Which property is typical of simple covalent compounds?", "Low melting point", ["Conducts electricity when solid", "Very high boiling point", "Dissolves in water to form ions always"], "Weak intermolecular forces need little energy to overcome, so melting points are low.", "Properties of compounds", "medium"),
    H("Element X has proton number 12. What is the formula of the compound formed between X and chlorine?", "XCl₂", ["XCl", "X₂Cl", "X₂Cl₃"], "X (2.8.2) forms X²⁺; chlorine forms Cl⁻. Two Cl⁻ balance one X²⁺.", "Ionic bonds", "hard"),
    H("Which pair of elements is most likely to form a covalent compound?", "Carbon and hydrogen", ["Sodium and chlorine", "Magnesium and oxygen", "Calcium and fluorine"], "Two non-metals share electrons to form covalent bonds.", "Covalent bonds", "easy"),
    H("What is the electron arrangement of a chloride ion, Cl⁻? (proton number of Cl = 17)", "2.8.8", ["2.8.7", "2.8.6", "2.8.8.1"], "Chlorine (2.8.7) gains one electron to become 2.8.8.", "Ionic bonds", "medium"),
    H("Why are noble gases unreactive?", "They have a stable duplet or octet electron arrangement", ["They have no electrons", "They are metals", "They have high melting points"], "A full outer shell means they do not need to gain, lose or share electrons.", "Stability of atoms", "easy"),
    H("Element Y has electron arrangement 2.6. Which bond does Y form with hydrogen?", "Covalent bond", ["Ionic bond", "Metallic bond", "No bond"], "Y (oxygen) and hydrogen are non-metals, so they share electrons.", "Covalent bonds", "hard"),
]

CELL = [
    H("Which organelle is the site of cellular respiration?", "Mitochondrion", ["Ribosome", "Nucleus", "Golgi apparatus"], "Mitochondria release energy from glucose through respiration.", "Organelles", "easy"),
    H("Which structure controls all the activities of the cell?", "Nucleus", ["Vacuole", "Cell wall", "Cytoplasm"], "The nucleus contains DNA and controls cell activities.", "Organelles", "easy"),
    H("Which structure is found in plant cells but not in animal cells?", "Chloroplast", ["Mitochondrion", "Ribosome", "Cell membrane"], "Chloroplasts carry out photosynthesis and are only in plant cells.", "Plant vs animal cells", "easy"),
    H("What is the function of ribosomes?", "Synthesise proteins", ["Store water", "Produce energy", "Control entry of substances"], "Ribosomes are the site of protein synthesis.", "Organelles", "medium"),
    H("What is the main component of the plant cell wall?", "Cellulose", ["Protein", "Lipid", "Starch"], "Cell walls are made of cellulose, giving the cell a fixed shape.", "Plant vs animal cells", "medium"),
    H("Which cell would have the MOST mitochondria?", "Muscle cell", ["Red blood cell", "Skin cell", "Fat cell"], "Muscle cells need a lot of energy, so they have many mitochondria.", "Cell specialisation", "hard"),
    H("Which structure controls the movement of substances into and out of the cell?", "Plasma membrane", ["Cell wall", "Nucleus", "Vacuole"], "The plasma membrane is partially permeable.", "Organelles", "easy"),
    H("What is the function of the Golgi apparatus?", "Modify, package and transport proteins", ["Carry out photosynthesis", "Store genetic information", "Break down glucose"], "The Golgi apparatus processes and packages proteins for transport.", "Organelles", "medium"),
    H("Which is the correct order of organisation in multicellular organisms?", "Cell → tissue → organ → system", ["Tissue → cell → organ → system", "Cell → organ → tissue → system", "Organ → tissue → cell → system"], "Cells form tissues, tissues form organs, and organs form systems.", "Cell organisation", "medium"),
    H("Why do plant cells not burst when placed in distilled water?", "The cell wall prevents bursting", ["They have no vacuole", "They lose water", "The nucleus controls it"], "The rigid cellulose cell wall resists the pressure of water entering.", "Plant vs animal cells", "hard"),
]

INDEPENDENCE = [
    H("When did the Federation of Malaya achieve independence?", "31 August 1957", ["16 September 1963", "1 February 1948", "9 August 1965"], "Tunku Abdul Rahman proclaimed independence at Stadium Merdeka on 31 August 1957.", "Merdeka", "easy"),
    H("Who was the first Prime Minister of the Federation of Malaya?", "Tunku Abdul Rahman", ["Tun Abdul Razak", "Dato' Onn Jaafar", "Tun Tan Cheng Lock"], "Tunku Abdul Rahman is known as Bapa Kemerdekaan.", "Merdeka", "easy"),
    H("When was Malaysia formed?", "16 September 1963", ["31 August 1957", "1 April 1946", "9 August 1965"], "Malaysia was formed by Malaya, Sabah, Sarawak and Singapore.", "Formation of Malaysia", "easy"),
    H("Which plan was strongly opposed because it reduced the power of the Malay Rulers?", "Malayan Union", ["Federation of Malaya", "Reid Commission", "Cobbold Commission"], "The Malayan Union (1946) transferred the Rulers' powers to the British Crown.", "Malayan Union", "medium"),
    H("Which party was founded in 1946 to oppose the Malayan Union?", "UMNO", ["MCA", "MIC", "PAS"], "UMNO was founded by Dato' Onn Jaafar in 1946.", "Malayan Union", "medium"),
    H("Which commission drafted the constitution of the Federation of Malaya?", "Reid Commission", ["Cobbold Commission", "Cheeseman Commission", "Barnes Commission"], "The Reid Commission, led by Lord Reid, drafted the 1957 constitution.", "Road to Merdeka", "medium"),
    H("Which parties formed the Alliance (Perikatan)?", "UMNO, MCA and MIC", ["UMNO, PAS and MCA", "MCA, MIC and DAP", "UMNO, MIC and Gerakan"], "The Alliance showed inter-ethnic cooperation, which convinced Britain to grant independence.", "Unity", "medium"),
    H("When was the Federation of Malaya established, replacing the Malayan Union?", "1 February 1948", ["31 August 1957", "1 April 1946", "16 September 1963"], "The Federation of Malaya Agreement restored the position of the Malay Rulers.", "Malayan Union", "hard"),
    H("Which commission gathered the views of the people of Sabah and Sarawak on forming Malaysia?", "Cobbold Commission", ["Reid Commission", "Razak Report", "Hertogh Commission"], "The Cobbold Commission (1962) found that most supported the formation of Malaysia.", "Formation of Malaysia", "hard"),
    H("In which year did Singapore separate from Malaysia?", "1965", ["1963", "1957", "1969"], "Singapore left Malaysia on 9 August 1965.", "Formation of Malaysia", "easy"),
]

TENSES = [
    H("She ___ to school every day.", "walks", ["walk", "walking", "walked"], "'Every day' shows a habit → simple present; 'she' takes verb + s.", "Simple present", "easy"),
    H("They ___ football when it started to rain.", "were playing", ["played", "are playing", "have played"], "An ongoing action interrupted in the past uses the past continuous.", "Past continuous", "medium"),
    H("I ___ my keys. I can't find them anywhere!", "have lost", ["lose", "had lost", "am losing"], "The past action has a result now → present perfect.", "Present perfect", "medium"),
    H("By the time we arrived, the movie ___.", "had started", ["has started", "starts", "was start"], "An action completed before another past action uses the past perfect.", "Past perfect", "hard"),
    H("Water ___ at 100°C.", "boils", ["boiled", "is boiling", "will boil"], "Scientific facts use the simple present.", "Simple present", "easy"),
    H("Look! The baby ___.", "is sleeping", ["sleeps", "slept", "has slept"], "'Look!' signals an action happening now → present continuous.", "Present continuous", "easy"),
    H("We ___ in Kuala Lumpur since 2018.", "have lived", ["lived", "live", "are living since"], "'Since' + a starting point → present perfect.", "Present perfect", "medium"),
    H("Ahmad ___ his grandmother last weekend.", "visited", ["visits", "has visited", "will visit"], "'Last weekend' is a finished time → simple past.", "Simple past", "easy"),
    H("If it rains tomorrow, we ___ indoors.", "will stay", ["stayed", "stay", "would stayed"], "First conditional: if + present, will + verb.", "Future", "medium"),
    H("Neither the teacher nor the students ___ aware of the change.", "were", ["was", "is", "has been"], "With 'neither...nor', the verb agrees with the nearer subject (students → were).", "Subject-verb agreement", "hard"),
]

IMBUHAN = [
    H("Ali ___ bola itu dengan kuat.", "menendang", ["ditendang", "tendangan", "bertendang"], "Ayat aktif menggunakan awalan me-: menendang.", "Awalan", "easy"),
    H("Surat itu ___ oleh Siti semalam.", "ditulis", ["menulis", "tulisan", "bertulis"], "Ayat pasif dengan 'oleh' menggunakan awalan di-.", "Awalan", "easy"),
    H("Perkataan 'pelajar' dibentuk menggunakan imbuhan jenis apa?", "Awalan", ["Akhiran", "Apitan", "Sisipan"], "pe- + ajar → pelajar. Imbuhan pe- ialah awalan.", "Jenis imbuhan", "easy"),
    H("Imbuhan dalam perkataan 'kebersihan' ialah ___.", "apitan ke-...-an", ["awalan ke-", "akhiran -an", "sisipan -er-"], "ke- + bersih + -an: imbuhan di depan dan di belakang serentak ialah apitan.", "Apitan", "medium"),
    H("Mereka ___ di padang setiap petang.", "bermain", ["mainan", "dimainkan", "memainkan"], "Kata kerja tak transitif menggunakan awalan ber-.", "Awalan", "easy"),
    H("Perkataan yang mengandungi sisipan ialah ___.", "gerigi", ["berlari", "makanan", "ditulis"], "gerigi = g + -er- + igi. -er- ialah sisipan.", "Sisipan", "hard"),
    H("Imbuhan dalam perkataan 'makanan' ialah ___.", "akhiran -an", ["awalan ma-", "apitan ma-...-an", "sisipan -ak-"], "makan + -an → makanan.", "Akhiran", "easy"),
    H("Pokok itu ___ oleh angin kencang.", "ditumbangkan", ["menumbangkan", "tumbangan", "bertumbang"], "Ayat pasif: apitan di-...-kan.", "Apitan", "medium"),
    H("Encik Ahmad ___ anaknya ke sekolah setiap pagi.", "menghantar", ["dihantar", "hantaran", "berhantar"], "Ayat aktif transitif menggunakan awalan meN- → menghantar.", "Awalan", "medium"),
    H("Pilih perkataan yang menggunakan apitan pe-...-an.", "pendidikan", ["pendidik", "didikan", "mendidik"], "pe- + didik + -an → pendidikan.", "Apitan", "hard"),
]

CLIMATE = [
    H("Which instrument is used to measure rainfall?", "Rain gauge", ["Anemometer", "Barometer", "Thermometer"], "A rain gauge collects and measures rainfall.", "Weather instruments", "easy"),
    H("What is the difference between weather and climate?", "Climate is the average weather over a long period", ["Weather lasts for 30 years", "Climate changes every day", "They mean the same thing"], "Climate is the average of weather conditions over about 30 years.", "Weather vs climate", "easy"),
    H("Which monsoon brings heavy rain to the east coast of Peninsular Malaysia?", "Northeast Monsoon", ["Southwest Monsoon", "Inter-monsoon", "Trade winds"], "The Northeast Monsoon (Nov–Mar) brings heavy rain and floods to the east coast.", "Monsoons", "medium"),
    H("Malaysia has which type of climate?", "Equatorial", ["Mediterranean", "Desert", "Temperate"], "Malaysia is near the equator: hot and wet throughout the year.", "Climate types", "easy"),
    H("Which instrument measures air pressure?", "Barometer", ["Hygrometer", "Anemometer", "Wind vane"], "A barometer measures atmospheric pressure.", "Weather instruments", "medium"),
    H("What does a hygrometer measure?", "Relative humidity", ["Wind direction", "Temperature", "Sunshine hours"], "A hygrometer measures the amount of water vapour in the air.", "Weather instruments", "medium"),
    H("Why does temperature decrease at higher altitudes such as Cameron Highlands?", "Air is thinner and holds less heat", ["It is closer to the sun", "There is more pollution", "There are more clouds at sea level"], "Thinner air at high altitude absorbs and retains less heat.", "Factors affecting climate", "hard"),
    H("During which months does the Southwest Monsoon usually occur?", "May to September", ["November to March", "January to April", "October to December"], "The Southwest Monsoon brings relatively drier weather from May to September.", "Monsoons", "hard"),
]

GENERATORS: dict[str, list[tuple]] = {
    "quadratic": [(q_quad_solve, 7), (q_quad_factorise, 5), (q_quad_general, 4), (q_quad_identify, 3), (q_quad_nature, 4), (q_quad_positive_root, 3)],
    "linear": [(q_lin_solve, 6), (q_lin_brackets, 4), (q_lin_simultaneous, 5), (q_lin_simultaneous_hard, 3), (q_lin_word, 4)],
    "functions": [(q_fn_eval, 6), (q_fn_inverse_value, 4), (q_fn_inverse_expr, 4), (q_fn_composite, 4), (q_fn_find_k, 4)],
    "trigonometry": [(q_trig_ratio, 8), (q_trig_pythag, 4), (q_trig_side, 4), (q_trig_special, 5)],
    "statistics": [(q_stat_mean, 5), (q_stat_median, 5), (q_stat_mode, 4), (q_stat_range, 4), (q_stat_missing, 3)],
    "indices": [(q_idx_multiply, 4), (q_idx_divide, 4), (q_idx_power, 4), (q_idx_eval, 4), (q_idx_coefficient, 3), (q_idx_negative, 3)],
    "differentiation": [(q_diff_power, 6), (q_diff_poly, 5), (q_diff_gradient, 5), (q_diff_find_x, 4)],
    "progressions": [(q_ap_nth, 6), (q_ap_diff, 5), (q_ap_sum, 4), (q_ap_which, 5)],
    "electricity": [(q_el_ohm, 8), (q_el_power, 4), (q_el_series, 3), (q_el_parallel, 3), (q_el_charge, 3), (q_el_combo, 3)],
    "forces": [(q_fm_velocity, 5), (q_fm_accel, 4), (q_fm_force, 4), (q_fm_find_accel, 4), (q_fm_momentum, 4), (q_fm_weight, 3)],
    "mole": [(q_mole_moles, 6), (q_mole_mass, 5), (q_mole_particles, 4), (q_mole_molar_mass, 5)],
}

STATIC: dict[str, list[dict]] = {
    "bonding": BONDING,
    "cell": CELL,
    "independence": INDEPENDENCE,
    "tenses": TENSES,
    "imbuhan": IMBUHAN,
    "climate": CLIMATE,
}


def build_questions(topic_key: str, rng: random.Random) -> list[dict]:
    if topic_key in STATIC:
        return [dict(q) for q in STATIC[topic_key]]
    out, seen = [], set()
    for fn, count in GENERATORS.get(topic_key, []):
        made, tries = 0, 0
        while made < count and tries < count * 20:
            tries += 1
            try:
                q = fn(rng)
            except AssertionError:  # degenerate parameters (duplicate options); draw again
                continue
            if q["text"] in seen:
                continue
            seen.add(q["text"])
            out.append(q)
            made += 1
    return out
