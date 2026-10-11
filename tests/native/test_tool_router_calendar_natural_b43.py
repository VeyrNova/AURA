import unittest
from datetime import date
from aura_native.tools.router import ToolRouter
class CalendarNaturalB43Tests(unittest.TestCase):
 def setUp(self): self.r=ToolRouter(None)
 def route(self,s): return self.r.route(s).arguments
 def test_ui_calendar_title_and_duration(self):
  a=self.route('Ajoute demain à 14h un rendez-vous TEST AURA UI CALENDAR pendant 30 minutes')
  self.assertEqual(a['title'],'TEST AURA UI CALENDAR'); self.assertTrue(a['start'].endswith('14:00:00+02:00')); self.assertTrue(a['end'].endswith('14:30:00+02:00'))
 def test_duration_variants(self):
  for text,end in [('pendant 15 minutes','14:15'),('pendant 45 minutes','14:45'),('pendant 1 heure','15:00'),('pendant 1h30','15:30')]:
   a=self.route('Ajoute demain à 14h un rendez-vous Test '+text); self.assertTrue(a['end'].endswith(end+':00+02:00'))
 def test_weekday_and_natural_titles(self):
  self.assertEqual(self.route('Crée un rendez-vous Contrôle ICPE vendredi à 10h pendant 45 minutes')['title'],'Contrôle ICPE')
  self.assertEqual(self.route('Créer demain à 11h l’événement Test simple')['title'],'Test simple')
