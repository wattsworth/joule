from tests.helpers import DbTestCase
from joule import update_users
from joule.models.master import Master
import tempfile

class TestUpdateUsers(DbTestCase):

   

    def test_adds_users_from_file(self):
        with tempfile.NamedTemporaryFile() as user_file:
            # 1. Create two users
            with open(user_file.name, 'w') as f:
                f.write("""
                # add two users
                johndoe, abcdefghijkl123
                # comments and blank lines should be ignored

                janedoe, 123abcdefghijkl
                """)
            update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)
            user1: Master = self.db.query(Master).filter_by(name="johndoe").one()
            user2: Master = self.db.query(Master).filter_by(name="janedoe").one()
            self.assertEqual(user1.key, "abcdefghijkl123")
            self.assertEqual(user1.type, Master.TYPE.USER)
            self.assertEqual(user2.key, "123abcdefghijkl")
            self.assertEqual(user2.type, Master.TYPE.USER)

            # 2. Update second user's API key
            with open(user_file.name, 'w') as f:
                f.write("""
                # change second user's key
                johndoe, abcdefghijkl123
                janedoe, 123zxyabcdefghijkl
                """)
            # should get a log message that johndoe is unchanged
            with self.assertLogs(level='INFO') as logs:
                update_users.update_users_from_file(user_file.name, self.db)
            log_output = " ".join(logs.output)
            self.assertIn("johndoe already exists with this key", log_output)
            self.assertIn("Modifying API key for janedoe", log_output)
            update_users.update_users_from_file(user_file.name, self.db)
            user1: Master = self.db.query(Master).filter_by(name="johndoe").one()
            user2: Master = self.db.query(Master).filter_by(name="janedoe").one()
            self.assertEqual(user1.key, "abcdefghijkl123")
            self.assertEqual(user1.type, Master.TYPE.USER)
            self.assertEqual(user2.key, "123zxyabcdefghijkl")
            self.assertEqual(user2.type, Master.TYPE.USER)
            
            # 3. Add two new users, remove first user
            with open(user_file.name, 'w') as f:
                f.write("""
                # add two new users, remove first
                DELETE johndoe
                newuser1, 456zxyabcdefghijkl
                newuser2, 789zxyabcdefghijkl
                """)
            update_users.update_users_from_file(user_file.name, self.db)
            self.assertEqual(self.db.query(Master).count(), 3)
            # make sure johndoe is deleted
            with self.assertRaises(Exception):
                self.db.query(Master).filter_by(name="johndoe").one()
            user3: Master = self.db.query(Master).filter_by(name="newuser1").one()
            user4: Master = self.db.query(Master).filter_by(name="newuser2").one()
            self.assertEqual(user3.key, "456zxyabcdefghijkl")
            self.assertEqual(user4.key, "789zxyabcdefghijkl")

            # 4. Remove users with a LIKE clause
            with open(user_file.name, 'w') as f:
                f.write("""
                # remove users with LIKE clause
                DELETE LIKE newuser%
                """)
            update_users.update_users_from_file(user_file.name, self.db)
            self.assertEqual(self.db.query(Master).count(), 1)
            with self.assertRaises(Exception):
                self.db.query(Master).filter_by(name="newuser1").one()
            with self.assertRaises(Exception):
                self.db.query(Master).filter_by(name="newuser2").one()
            # there should only be one user left
            user2: Master = self.db.query(Master).filter_by(name="janedoe").one()
            self.assertEqual(user2.key, "123zxyabcdefghijkl")
            self.assertEqual(user2.type, Master.TYPE.USER)

    def test_errors_on_adds_users_from_file(self):
        with tempfile.NamedTemporaryFile() as user_file:
            # create two users
            with open(user_file.name, 'w') as f:
                f.write("""
                # add two users
                johndoe, abcdefghijkl123
                janedoe, 123abcdefghijkl
                """)
            update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)

        # 1. invalid syntax
        with tempfile.NamedTemporaryFile() as user_file:
            with open(user_file.name, 'w') as f:
                f.write("""
                this is an error
                """)
            with self.assertLogs(level='ERROR'):
                update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)
        
        # 2. invalid delete syntax
        with tempfile.NamedTemporaryFile() as user_file:
            with open(user_file.name, 'w') as f:
                f.write("""
                DELETE ALL johndoe%
                """)
            with self.assertLogs(level='ERROR'):
                update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)

        # 3. invalid delete syntax
        with tempfile.NamedTemporaryFile() as user_file:
            with open(user_file.name, 'w') as f:
                f.write("""
                DELETEALL johndoe
                """)
            with self.assertLogs(level='ERROR'):
                update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)

        # 4. invalid delete syntax
        with tempfile.NamedTemporaryFile() as user_file:
            with open(user_file.name, 'w') as f:
                f.write("""
                DELETE TOO MANY PARAMS johndoe
                """)
            with self.assertLogs(level='ERROR'):
                update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)

        # 5. cannot have duplicate API keys
        with tempfile.NamedTemporaryFile() as user_file:
            with open(user_file.name, 'w') as f:
                f.write("""
                newuser, 123abcdefghijkl
                """)
            with self.assertLogs(level='ERROR'):
                update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)

        # 6. key too short
        with tempfile.NamedTemporaryFile() as user_file:
            with open(user_file.name, 'w') as f:
                f.write("""
                newuser, abcdef
                """)
            with self.assertLogs(level='ERROR'):
                update_users.update_users_from_file(user_file.name, self.db)
            # make sure both users are in the database
            self.assertEqual(self.db.query(Master).count(), 2)
