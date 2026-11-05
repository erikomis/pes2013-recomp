import unittest
from propose_pes_identities import propose


class IdentityProposalTests(unittest.TestCase):
    def test_homonyms_stay_ambiguous_and_excluded_players_stay_out(self):
        squads = {'clubs': [{'name': 'Club', 'draft_squad_ids': ['1'], 'athletes': [
            {'cbf_id': '1', 'name': 'José da Silva', 'display_name': 'José'},
            {'cbf_id': '2', 'name': 'Other', 'display_name': 'Other'}]}]}
        database = {'players': [
            {'id': 10, 'name': 'JOSE', 'shirt_name': 'JOSE'},
            {'id': 11, 'name': 'JOSÉ', 'shirt_name': 'JOSE'}]}
        result = propose(squads, database)
        self.assertEqual(result['summary']['total'], 1)
        self.assertEqual(result['summary']['ambiguous'], 1)
        self.assertFalse(result['rows'][0]['identity_verified'])
        self.assertIsNone(result['rows'][0]['face_id'])


if __name__ == '__main__':
    unittest.main()
