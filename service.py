"""Compatibility imports. Application Model now lives in models.restaurant."""
from models.restaurant import (
    ROOT, TZ, Problem, Restaurant, require, money, integer, string, phone,
    password_hash, rows, one, rows_as_pairs,
)

__all__ = [
    'ROOT', 'TZ', 'Problem', 'Restaurant', 'require', 'money', 'integer',
    'string', 'phone', 'password_hash', 'rows', 'one', 'rows_as_pairs',
]
