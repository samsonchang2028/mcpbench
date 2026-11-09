"""Offline compatibility/negative tests for rendered external network contracts."""
from copy import deepcopy
import unittest

from containers.check_config import validate_external_networks


class ExternalNetworksTests(unittest.TestCase):
    def setUp(self):
        self.networks = {"db": {"name": "mcpbench_db", "external": True},
                         "front": {"name": "mcpbench_front", "external": True}}

    def test_absent_or_empty_ipam(self):
        for include_db in (False, True):
            for include_front in (False, True):
                with self.subTest(db=include_db, front=include_front):
                    networks = deepcopy(self.networks)
                    if include_db:
                        networks["db"]["ipam"] = {}
                    if include_front:
                        networks["front"]["ipam"] = {}
                    validate_external_networks(networks)

    def test_rejects_changed_network_contract(self):
        mutations = [
            ("ipam", {"config": [{"subnet": "172.20.0.0/24"}]}),
            ("ipam", None), ("ipam", []), ("external", False),
            ("external", 1), ("name", "unowned"),
            ("internal", True), ("internal", False), ("driver", "bridge"),
            ("unknown", {}),
        ]
        for role in ("db", "front"):
            for key, value in mutations:
                with self.subTest(role=role, key=key, value=value):
                    networks = deepcopy(self.networks)
                    networks[role][key] = value
                    with self.assertRaises(AssertionError):
                        validate_external_networks(networks)
            for missing in ("external", "name"):
                with self.subTest(role=role, missing=missing):
                    networks = deepcopy(self.networks)
                    del networks[role][missing]
                    with self.assertRaises(AssertionError):
                        validate_external_networks(networks)

    def test_rejects_added_or_missing_network(self):
        for networks in ({"db": self.networks["db"]},
                         {**self.networks, "extra": self.networks["db"]}):
            with self.assertRaises(AssertionError):
                validate_external_networks(networks)
