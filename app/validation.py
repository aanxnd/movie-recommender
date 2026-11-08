"""Public validation diagnostics must never serialize submitted values.

Pydantic's input, context, message, custom type, and mapping-key locations can
all contain user data. Project onto fixed messages and known schema locations
instead of trying to recognize every possible spelling of a credential field.
"""

MESSAGES = {
    "missing": "Field is required.",
    "int_type": "Enter a whole number.",
    "int_parsing": "Enter a whole number.",
    "int_from_float": "Enter a whole number.",
    "float_type": "Enter a number.",
    "float_parsing": "Enter a number.",
    "finite_number": "Enter a finite number.",
    "string_type": "Enter text.",
    "string_too_short": "Text is shorter than the allowed minimum.",
    "string_too_long": "Text exceeds the allowed maximum length.",
    "greater_than": "Value must exceed the allowed minimum.",
    "greater_than_equal": "Value is below the allowed minimum.",
    "less_than": "Value must be below the allowed maximum.",
    "less_than_equal": "Value exceeds the allowed maximum.",
    "multiple_of": "Value must use the required increment.",
    "list_type": "Enter a list.",
    "dict_type": "Enter an object.",
    "too_short": "Too few items.",
    "too_long": "Too many items.",
    "json_invalid": "Malformed JSON body.",
    "model_attributes_type": "Enter an object with the required fields.",
    "model_type": "Enter an object with the required fields.",
    "extra_forbidden": "Unexpected field.",
    "literal_error": "Choose an allowed value.",
    "bool_type": "Enter a boolean value.",
    "value_error": "Invalid value.",
}
LOCATIONS = frozenset({
    "body", "query", "path", "header", "cookie", "authorization",
    "rating", "movie_id", "movie_ids", "user_id", "user_ids", "invitations",
    "q", "limit", "min_rating_count", "decade", "after", "genre",
})
LIST_FIELDS = frozenset({"movie_ids", "user_ids"})


def public_validation_errors(errors):
    details = []
    for error in errors:
        code = error.get("type")
        code = code if isinstance(code, str) and code in MESSAGES else "value_error"
        location = []
        previous = None
        parts = error.get("loc", ())
        for part in parts if isinstance(parts, (list, tuple)) else ():
            if previous == "invitations":
                # Dict keys are client-controlled, even when validation fails.
                location.append("member")
            elif isinstance(part, str) and part in LOCATIONS:
                location.append(part)
            elif type(part) is int and previous in LIST_FIELDS and 0 <= part <= 100:
                location.append(part)
            else:
                location.append("field")
            previous = part if isinstance(part, str) and part in LOCATIONS else None
        details.append({"type": code, "loc": location, "msg": MESSAGES[code]})
    return details
