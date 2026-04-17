"""
logger.py – Centralised logging setup.

Produces:
  • Coloured output on the console (INFO and above)
  • A plain-text rolling file at logs/pipeline.log (DEBUG and above)
  • A separate data-quality log at logs/data_quality.log
"""

import logging
import sys
from pathlib import Path



def get_logger(name, log_file=None):
    """Return a named logger, initialising handlers only once."""
    logger = logging.getLogger(name)

    if logger.handlers:          # already configured – avoid duplicate handlers
        return logger

    logger.setLevel(logging.DEBUG)

    #  Console handler 
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler 
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s – %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)

    return logger


def get_quality_logger(log_file):
    """Dedicated logger that writes data-quality events to its own file."""
    logger = logging.getLogger("data_quality")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)
    # Also mirror to stdout
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)
    return logger


