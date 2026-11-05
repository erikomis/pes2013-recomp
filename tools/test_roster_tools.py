"""Synthetic checks: no copyrighted game fixture or network required."""
import json
import struct
import unittest

from collect_cbf_rosters import athletes_from_html, clubs_from_html, normalize_club
from enrich_cbf_rosters import appearances, profile_from_html
import pes2013_edit as edit
from report_brazil_rosters import match_team
from merge_squad_evidence import identity_candidates
from collect_recent_squads import match_evidence
from datetime import date


def html_payload(value):
    return '<script>self.__next_f.push(' + json.dumps([1, '1:' + json.dumps({"data": value})]) + ')</script>'


def fixture():
    data = bytearray(edit.SIZE)
    data[:4] = bytes.fromhex("01000601")
    for slot in range(edit.PLAYER_COUNT):
        struct.pack_into(">I", data, edit.PLAYER_TABLE + slot * edit.PLAYER_STRIDE, 0xFFFFFFFF)
    struct.pack_into(">I", data, edit.PLAYER_TABLE, 123)
    data[edit.PLAYER_TABLE + 50:edit.PLAYER_TABLE + 55] = b"TEST\0"
    for slot in range(edit.CREATED_COUNT):
        struct.pack_into(">I", data, edit.CREATED_TABLE + slot * edit.PLAYER_STRIDE, 0x100000 + slot)
    for slot in range(edit.TEAM_COUNT):
        off = edit.TEAM_TABLE + slot * edit.TEAM_STRIDE
        struct.pack_into(">H", data, off + 1444, slot + 1)
        struct.pack_into(">H", data, off + 1456, slot + 1)
    for slot in range(edit.ROSTER_COUNT):
        off = edit.ROSTER_TABLE + slot * edit.ROSTER_STRIDE
        struct.pack_into(">H", data, off, slot + 1)
        struct.pack_into(">I", data, off + 4, 123)
        data[off + 132] = 10
    struct.pack_into(">I", data, 8, edit.crc32(data))
    return data


class EditTests(unittest.TestCase):
    def test_membership_and_shirt_number(self):
        data = fixture()
        before = bytes(data)
        result = edit.decode(data)
        self.assertEqual(result["teams"][0]["roster"]["members"][0]["name"], "TEST")
        self.assertEqual(result["teams"][0]["roster"]["members"][0]["shirt_number"], 10)
        self.assertEqual(bytes(data), before)

    def test_rejects_corruption(self):
        data = fixture()
        data[1000] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC32"):
            edit.decode(data)

    def test_rejects_broken_reference_even_with_valid_crc(self):
        data = fixture()
        struct.pack_into(">I", data, edit.ROSTER_TABLE + 4, 987654)
        struct.pack_into(">I", data, 8, edit.crc32(data))
        with self.assertRaisesRegex(ValueError, "Unresolved player"):
            edit.decode(data)

    def test_rejects_foreign_layout(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            edit.decode(bytes(100))


class CbfTests(unittest.TestCase):
    def test_ambiguous_player_names_remain_ambiguous(self):
        athlete = dict(name="Pedro Alves", display_name="Pedro")
        references = [dict(full_name="Pedro Silva", display_name="Pedro"),
                      dict(full_name="Pedro Alves", display_name="Pedro")]
        _, candidates = identity_candidates(athlete, references)
        self.assertEqual(len(candidates), 2)

    def test_shirt_number_alone_cannot_match_identity(self):
        athlete = dict(name="Pedro Alves", display_name="Pedro", shirt_number=9)
        reference = dict(full_name="Lucas Silva", display_name="Lucas", shirt_number=9)
        self.assertEqual(identity_candidates(athlete, [reference])[1], [])

    def test_match_extract_omits_photo_identifiers(self):
        athlete = dict(id="123", numero_camisa="42", reserva="true", goleiro="true",
                       entrou_jogando="false", nome="42 - Teste", apelido="42 - Teste", foto="not-for-export")
        side = dict(id="1", nome="Clube", atletas=[athlete])
        data = html_payload(dict(jogo=dict(id_jogo="10", mandante=side, visitante=dict(side, id="2"))))
        result = match_evidence(data, "https://example.com", "2026-10-29", "10")
        self.assertNotIn("foto", result["teams"][0]["athletes"][0])
        self.assertEqual(result["teams"][0]["athletes"][0]["name"], "Teste")
        self.assertFalse(result["teams"][0]["athletes"][0]["started"])
        with self.assertRaisesRegex(ValueError, "Wrong match"):
            match_evidence(data, "https://example.com", "2026-10-29", "11")

    def test_club_normalization(self):
        self.assertEqual(normalize_club("Atlético Mineiro  - MG"), "atletico mineiro")
        self.assertEqual(normalize_club("Coritiba SAF"), "coritiba")

    def test_botafogo_states_and_continental_variants_are_distinct(self):
        teams = [dict(id=100, name="BOTAFOGO", roster={}),
                 dict(id=0x4100, name="BOTAFOGO", roster={})]
        self.assertEqual(match_team(dict(name="Botafogo - SP"), teams), [])
        self.assertEqual(len(match_team(dict(name="Botafogo - RJ"), teams)), 1)

    def test_incomplete_club_page_fails(self):
        with self.assertRaisesRegex(ValueError, "20 clubs"):
            clubs_from_html("<html>Error</html>", "a", 2026)

    def test_missing_athlete_payload_fails(self):
        with self.assertRaisesRegex(ValueError, "No public athlete"):
            athletes_from_html("<html>Error</html>")

    def test_registration_payload(self):
        record = {"atleta_id": "123", "atleta_nome": "Teste", "Atleta_apelido": "Teste", "clube_nome_popular": "Clube"}
        self.assertEqual(athletes_from_html(html_payload({"atletas": [record]})), [record])

    def test_profile_and_cutoff(self):
        matches = [dict(codigo_time_mandante="1", codigo_time_visitante="2", encerrado=True, data=d)
                   for d in ["01/11/2026", "01/11/2026", "05/11/2026"]]
        value = dict(atleta_id="123", atleta_nome="Teste", atleta_apelido="Teste", atleta_data_nascimento="01/01/1990",
                     atleta_time_atual={}, atleta_estatisticas={}, jogos={"Brasileiro": {"A": matches}})
        result = profile_from_html(html_payload(value))
        self.assertEqual(appearances(result, "1", date(2026, 11, 4)), [date(2026, 11, 1)])
        self.assertEqual(appearances(result, "3", date(2026, 11, 4)), [])


if __name__ == "__main__":
    unittest.main()
