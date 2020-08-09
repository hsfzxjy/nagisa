import os
import shutil
import tempfile
import unittest

import torch

from nagisa.dl.torch.misc.io import load_state_dict
from nagisa.dl.torch.misc.testing import TorchTestCase
from nagisa.core.misc.io import download_url_to_file, prepare_resource

skip_if_local = unittest.skipIf(os.getenv("LOCAL") is not None, "local testing")

skip_if_local_and_no_proxy = unittest.skipIf(
    "proxychains" not in os.environ.get("LD_PRELOAD", "") and os.getenv("LOCAL") is not None,
    "local testing and no proxy",
)


class BaseTestCase(TorchTestCase):
    expected_data = {
        'tensor': torch.tensor(range(100), dtype=float),
        'string': 'hello world',
    }

    def tearDown(self):
        os.close(self.fd)
        if os.path.exists(self.dest):
            os.remove(self.dest)
        shutil.rmtree(self.dest_dir, ignore_errors=True)

    def setUp(self):
        self.fd, self.dest = tempfile.mkstemp()
        self.dest_dir = tempfile.mkdtemp()


class TestDownloadUrlToFile(BaseTestCase):
    @skip_if_local_and_no_proxy
    def test_small_file(self):
        download_url_to_file(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            self.dest,
            hash_prefix="cf7562b422f97f6b3d6dbfd9394df928735422becd8ab2d8d1c9902f2c15a077",
        )

        data = torch.load(self.dest)
        self.assertEqual(torch.load(self.dest), self.expected_data)

    @skip_if_local
    def test_big_file(self):
        # A ~40MB zip file which requires confirm code
        download_url_to_file(
            "https://drive.google.com/file/d/1X0NTkVNlXBvC0uRj1vWl4Ow7MA4bNQtk/view",
            self.dest,
            hash_prefix="71c70feee092db533f959362f866896afa59a57fb04c290f16667a37882589d3",
        )


class TestLoadStateDict(BaseTestCase):
    def test_load_local_small_file(self):
        torch.save(
            self.expected_data, self.dest,
            **(
                {
                    '_use_new_zipfile_serialization': False
                } if torch.__version__.startswith('1.6.') else {}
            )
        )
        loaded_data = load_state_dict(self.dest, model_dir=self.dest_dir)

        self.assertEqual(self.expected_data, loaded_data)

    @skip_if_local_and_no_proxy
    def test_small_file(self):
        data = load_state_dict(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            model_dir=self.dest_dir,
        )

        self.assertEqual(data, self.expected_data)

    @skip_if_local_and_no_proxy
    def test_small_file_to_custom_dir(self):
        data = load_state_dict(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            model_dir=self.dest_dir,
        )

        self.assertEqual(self.expected_data, data)

    @skip_if_local_and_no_proxy
    def test_big_file(self):
        # A ~40MB zip file which requires confirm code
        self.dest = prepare_resource(
            "https://drive.google.com/file/d/1X0NTkVNlXBvC0uRj1vWl4Ow7MA4bNQtk/view",
            self.dest_dir,
            check_hash="71c70feee092db533f959362f866896afa59a57fb04c290f16667a37882589d3",
        )
