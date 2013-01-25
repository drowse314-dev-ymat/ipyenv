# encoding: utf-8
"""
    ipyenv test helpers
    ~~~~~~~~~~~~~~~~~~~
"""

import os


def get_abspath_from(relpath_from_file):
    """Get absolute path."""
    return os.sep.join(
        (
            os.path.dirname(os.path.realpath(__file__)),
            relpath_from_file
        )
    )
