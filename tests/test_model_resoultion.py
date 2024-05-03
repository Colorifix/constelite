import json
from unittest import TestCase

from constelite.models import StateModel, resolve_model

class Character(StateModel):
    name: str


class Hero(Character):
    name: str
    power: str

class TestModelResolution(TestCase):
    def test_validate_character(self):
        character = Character(name="Harry")
        self.assertEqual(character.__class__, Character)
    
    def test_validate_hero(self):
        character = Character(
            name="Harry",
            power="magic",
            model_name="Hero"
        )
        
        hero = resolve_model(json.loads(character.json()))

        self.assertEqual(hero.__class__, Hero)
        self.assertEqual(hero.power, "magic")
