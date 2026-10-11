import unittest
from aura_native.developer_fabric.qt_bridge import DeveloperAgentsModel
from PySide6.QtCore import QModelIndex, Qt
class ModelTests(unittest.TestCase):
 def test_agents_dynamic_count(self):
  m=DeveloperAgentsModel([]); seen=[]; m.countChanged.connect(lambda:seen.append(m.count)); m.append_item({'displayName':'A'}); self.assertEqual(m.count,1); self.assertTrue(seen)
 def test_replace_model_reset(self):
  m=DeveloperAgentsModel([{'displayName':'A'}]); m.replace_items([{'displayName':'B'},{'displayName':'C'}]); self.assertEqual(m.count,2); self.assertEqual(m.data(m.index(0,0),257), 'B')
 def test_valid_row_valid_role(self):
  m=DeveloperAgentsModel([{'displayName':'A'}]); self.assertEqual(m.data(m.index(0,0),Qt.UserRole+1),'A')
 def test_invalid_index(self):
  self.assertIsNone(DeveloperAgentsModel([{}]).data(QModelIndex(),Qt.UserRole))
 def test_negative_row(self):
  m=DeveloperAgentsModel([{}]); self.assertIsNone(m.data(m.createIndex(-1,0),Qt.UserRole))
 def test_row_past_end(self):
  m=DeveloperAgentsModel([{}]); self.assertIsNone(m.data(m.createIndex(1,0),Qt.UserRole))
 def test_invalid_roles(self):
  m=DeveloperAgentsModel([{}])
  for role in (Qt.DisplayRole,-1,Qt.UserRole+100,b'unknown'):
   with self.subTest(role=role): self.assertIsNone(m.data(m.index(0,0),role))
 def test_role_mapping_all_models(self):
  from aura_native.developer_fabric.qt_bridge import DeveloperProjectsModel,DeveloperJobsModel,DeveloperProvidersModel
  for kind in (DeveloperAgentsModel,DeveloperProjectsModel,DeveloperJobsModel,DeveloperProvidersModel):
   m=kind([{key:key for key in kind.role_names}])
   for role,name in m.roleNames().items():
    with self.subTest(model=kind.__name__,role=role): self.assertEqual(m.data(m.index(0,0),role),name.decode())
 def test_empty_model(self):
  m=DeveloperAgentsModel(); self.assertIsNone(m.data(m.createIndex(0,0),Qt.UserRole))
 def test_reset_notifications_and_stale_row(self):
  m=DeveloperAgentsModel([{}]); old=m.index(0,0); seen=[]
  m.modelAboutToBeReset.connect(lambda:seen.append(('before',m.count)))
  m.modelReset.connect(lambda:seen.append(('after',m.count)))
  m.replace_items([]); self.assertEqual(seen,[('before',1),('after',0)]); self.assertIsNone(m.data(old,Qt.UserRole))
 def test_insert_notifications(self):
  m=DeveloperAgentsModel(); seen=[]
  m.rowsAboutToBeInserted.connect(lambda parent,first,last:seen.append(('before',first,last,m.count)))
  m.rowsInserted.connect(lambda parent,first,last:seen.append(('after',first,last,m.count)))
  m.append_item({'agentId':'a'}); self.assertEqual(seen,[('before',0,0,0),('after',0,0,1)])
 def test_child_and_foreign_index_rejected(self):
  m=DeveloperAgentsModel([{}]); other=DeveloperAgentsModel([{}]); self.assertEqual(m.rowCount(m.index(0,0)),0); self.assertIsNone(m.data(other.index(0,0),Qt.UserRole)); self.assertIsNone(m.data(m.createIndex(0,1),Qt.UserRole))
if __name__=='__main__': unittest.main()


