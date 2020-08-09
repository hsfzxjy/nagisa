import os
import re
import sys
import shutil
import tempfile
import unittest

from nagisa.core.misc.testing import ReloadModuleTestCase


class TestLogging(ReloadModuleTestCase):

    drop_modules = [
        '^nagisa',
        '^logging',
    ]
    attach = [
        ['contrib_logging', 'nagisa.contrib.logging'],
        ['logging', 'logging'],
    ]

    def tearDown(self):
        if hasattr(self, 'logdir'):
            shutil.rmtree(self.logdir, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.contrib_logging.init_logging()
        self.logdir = tempfile.mkdtemp()

    def get_content(self, filename):
        with open(os.path.join(self.logdir, filename), 'r') as f:
            return f.read()

    def test_logger_class(self):
        self.assertIsInstance(self.logging.getLogger('nagisa'), self.contrib_logging._Logger)

    def test_log_to_file_txt_ext(self):
        self.contrib_logging.setup_logger(os.path.join(self.logdir, "test_log.txt"))
        logger = self.logging.getLogger("nagisa.null")
        logger.info("test")
        self.assertIn(
            "nagisa.null INFO: test",
            self.get_content("test_log.txt"),
        )

    def test_log_to_file_log_ext(self):
        self.contrib_logging.setup_logger(os.path.join(self.logdir, "test_log.log"))
        logger = self.logging.getLogger("nagisa.null")
        logger.info("test")
        self.assertIn(
            "nagisa.null INFO: test",
            self.get_content("test_log.log"),
        )

    def test_log_to_file_dir(self):
        self.contrib_logging.setup_logger(os.path.join(self.logdir))
        logger = self.logging.getLogger("nagisa.null")
        logger.info("test")
        self.assertIn(
            "nagisa.null INFO: test",
            self.get_content("log.txt"),
        )

    def test_log_to_file_txt_ext_slave_worker(self):
        self.contrib_logging.setup_logger(
            os.path.join(self.logdir, "test_log.txt"), distributed_rank=1
        )
        logger = self.logging.getLogger("nagisa.null")
        logger.info("test")
        self.assertIn(
            "nagisa.null INFO: test",
            self.get_content("test_log.txt.rank1"),
        )

    def log_twice(self, logger):
        logger.log_first_n("test", n=2)

    def test_log_twice(self):
        self.contrib_logging.setup_logger(os.path.join(self.logdir))
        logger = self.logging.getLogger("nagisa.null")
        self.log_twice(logger)
        self.log_twice(logger)
        self.log_twice(logger)
        self.assertRegexpMatches(
            self.get_content("log.txt"),
            re.compile(r'[^\n]*nagisa.null INFO: test\n.*nagisa.null INFO: test\n', re.M)
        )

    def log_once(self, logger):
        logger.log_once("test")

    def test_log_once(self):
        self.contrib_logging.setup_logger(os.path.join(self.logdir))
        logger = self.logging.getLogger("nagisa.null")
        self.log_once(logger)
        self.log_once(logger)
        self.log_once(logger)
        self.assertRegexpMatches(
            self.get_content("log.txt"), re.compile(r'[^\n]*nagisa.null INFO: test\n', re.M)
        )

    def log_every_three_times(self, logger):
        logger.log_every_n("test", n=3)

    def test_log_every_three_times(self):
        self.contrib_logging.setup_logger(os.path.join(self.logdir))
        logger = self.logging.getLogger("nagisa.null")

        for _ in range(6):
            self.log_every_three_times(logger)

        self.assertRegexpMatches(
            self.get_content("log.txt"),
            re.compile(r'[^\n]*nagisa.null INFO: test\n.*nagisa.null INFO: test\n', re.M)
        )

    def log_every_one_second(self, logger):
        logger.log_every_n_seconds("test", n=1)

    @unittest.skipIf(os.getenv("LOCAL") is not None, "local testing")
    def test_log_every_one_tenth_second(self):
        import time

        self.contrib_logging.setup_logger(os.path.join(self.logdir))
        logger = self.logging.getLogger("nagisa.null")

        for _ in range(12):
            time.sleep(0.1)
            self.log_every_one_second(logger)

        self.assertRegexpMatches(
            self.get_content("log.txt"), re.compile(r'[^\n]*nagisa.null INFO: test\n', re.M)
        )
