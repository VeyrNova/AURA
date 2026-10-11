import unittest
from datetime import date, timedelta
from aura_native.tools.router import ToolRouter
from aura_native.tools.models import ToolRouteResult

class ExplodingRegistry:
 def execute(self,*_): raise AssertionError('router executed a tool')

class ToolRouterA32Tests(unittest.TestCase):
 def setUp(self): self.router=ToolRouter(ExplodingRegistry())
 def route(self,text):
  result=self.router.route(text); self.assertIsInstance(result,ToolRouteResult); return result
 def test_calendar_reads(self):
  self.assertEqual(self.route('Quels sont mes prochains rendez-vous ?').tool_name,'calendar.list_events')
  tomorrow=self.route("Qu'est-ce que j'ai demain ?"); self.assertEqual(tomorrow.tool_name,'calendar.get_day'); self.assertEqual(tomorrow.arguments['date'],(date.today()+timedelta(days=1)).isoformat())
  self.assertEqual(self.route("Qu'est-ce que j'ai vendredi ?").tool_name,'calendar.get_day')
  free=self.route('Est-ce que je suis libre demain après-midi ?'); self.assertEqual(free.tool_name,'calendar.find_free_time'); self.assertEqual(free.arguments['part_of_day'],'afternoon')
 def test_calendar_writes_are_routes_only(self):
  create=self.route('Ajoute dentiste vendredi à 15h'); self.assertEqual(create.tool_name,'calendar.prepare_create_event'); self.assertFalse(create.needs_clarification); self.assertEqual(create.arguments['title'],'dentiste'); self.assertIn('start',create.arguments); self.assertIn('end',create.arguments)
  self.assertEqual(self.route('Crée une réunion projet mardi de 14h à 15h').tool_name,'calendar.prepare_create_event')
  update=self.route('Décale mon rendez-vous dentiste à 16h'); self.assertEqual(update.tool_name,'calendar.prepare_update_event'); self.assertEqual(update.arguments['target'],'dentiste à 16h')
  delete=self.route('Supprime ma réunion de 14h'); self.assertEqual(delete.tool_name,'calendar.prepare_delete_event')
 def test_tasks_and_weather(self):
  self.assertEqual(self.route('Quelles sont mes tâches ?').tool_name,'tasks.list')
  self.assertEqual(self.route('Rappelle-moi de relancer Marc demain').tool_name,'tasks.prepare_create')
  self.assertEqual(self.route('Marque acheter du lait comme terminé').tool_name,'tasks.prepare_complete')
  self.assertEqual(self.route('Supprime la tâche acheter du lait').tool_name,'tasks.prepare_delete')
  weather=self.route('Météo à Nice demain'); self.assertEqual(weather.tool_name,'weather.get_forecast'); self.assertEqual(weather.arguments['location'],'Nice')
 def test_no_match_clarification_and_determinism(self):
  self.assertIsNone(self.router.route('Explique-moi Python'))
  self.assertTrue(self.route('Ajoute une réunion').needs_clarification)
  self.assertTrue(self.route('Ajoute une tâche').needs_clarification)
  self.assertTrue(self.route('Supprime mon rendez-vous').needs_clarification)
  self.assertEqual(self.router.route('Ajoute dentiste vendredi à 15h'),self.router.route('Ajoute dentiste vendredi à 15h'))

if __name__=='__main__': unittest.main()