"""Parse Indian job salary strings into LPA."""

import re


def parse_salary_lpa(salary_text: str | None) -> tuple[float, float] | None:
    """
    Parse salary text to (min_lpa, max_lpa).
    Returns None if undisclosed or unparseable.
    """
    if not salary_text:
        return None

    text = salary_text.lower().replace(",", "").replace("₹", "").strip()
    if any(x in text for x in ("not disclosed", "undisclosed", "as per industry", "best in")):
        return None

    # Range: 10-15 LPA, 10 to 15 lacs
    range_match = re.search(
        r"(\d+\.?\d*)\s*(?:-|–|to)\s*(\d+\.?\d*)\s*(?:lpa|lacs|lac|lakh|lakhs?)\b",
        text,
    )
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        return (min(a, b), max(a, b))

    # Single: 12 LPA
    single = re.search(r"(\d+\.?\d*)\s*(?:lpa|lacs|lac|lakh|lakhs?)\b", text)
    if single:
        v = float(single.group(1))
        return (v, v)

    # Monthly: 1,00,000 per month → LPA
    monthly = re.search(r"(\d+\.?\d*)\s*(?:per month|/month|p\.?m\.?|pm)\b", text)
    if monthly:
        lpa = float(monthly.group(1)) * 12 / 100_000
        return (lpa, lpa)

    # Raw lakhs without unit in short strings: "10-12"
    if "lpa" not in text and "lac" not in text:
        nums = [float(n) for n in re.findall(r"(\d+\.?\d*)", text)]
        if 2 <= len(nums) <= 3 and all(n < 100 for n in nums):
            if len(nums) >= 2:
                return (min(nums[0], nums[1]), max(nums[0], nums[1]))
            if nums[0] >= 3:
                return (nums[0], nums[0])

    return None


def is_salary_eligible(salary_text: str | None, min_lpa: float) -> bool:
    """True if salary meets minimum, undisclosed, or min filter disabled (0)."""
    if min_lpa <= 0:
        return True
    parsed = parse_salary_lpa(salary_text)
    if parsed is None:
        return True
    _min, max_lpa = parsed
    return max_lpa >= min_lpa


def salary_meets_minimum(salary_text: str | None, min_lpa: float) -> bool | None:
    """True/False if parseable, None if undisclosed. Disabled when min_lpa <= 0."""
    if min_lpa <= 0:
        return None
    parsed = parse_salary_lpa(salary_text)
    if parsed is None:
        return None
    return parsed[1] >= min_lpa


def format_salary_check(salary_text: str | None, min_lpa: float) -> str:
    parsed = parse_salary_lpa(salary_text)
    if parsed is None:
        return "Salary undisclosed"
    lo, hi = parsed
    if min_lpa <= 0:
        return f"₹{lo:.0f}–{hi:.0f} LPA" if lo != hi else f"₹{hi:.0f} LPA"
    if hi >= min_lpa:
        return f"₹{lo:.0f}–{hi:.0f} LPA ✓" if lo != hi else f"₹{hi:.0f} LPA ✓"
    return f"₹{lo:.0f}–{hi:.0f} LPA ✗ (below {min_lpa:.0f})"
