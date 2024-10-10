from firebase_admin import auth

class FirebaseService:
    @staticmethod
    def verify_id_token(id_token):
        try:
            return auth.verify_id_token(id_token)
        except ValueError:
            return None

    @staticmethod
    def get_user(uid):
        try:
            return auth.get_user(uid)
        except auth.UserNotFoundError:
            return None

    @staticmethod
    def update_user_password(uid, new_password):
        try:
            # Update the user's password
            user = auth.update_user(
                uid,
                password=new_password
            )
            print(f"Successfully updated user: {user.uid}")
            return user
        except Exception as e:
            print(f"Error updating user password: {e}")
            return None