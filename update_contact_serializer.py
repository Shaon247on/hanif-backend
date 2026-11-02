import sys

filepath = 'apps/contact/serializers.py'
with open(filepath, 'r') as f:
    content = f.read()

old_block = """class ContactUserSerializer(serializers.ModelSerializer):
    \"\"\"Serializer for contacts / customer users (role='USER').\"\"\"

    image = ExtendedImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "phone",
            "image",
            "address",
            "role",
            "status",
            "last_active_at",
            "date_joined",
        )
        read_only_fields = ("id", "role", "status", "last_active_at", "date_joined")"""

new_block = """class ContactUserSerializer(serializers.ModelSerializer):
    \"\"\"Serializer for contacts / customer users (role='USER').\"\"\"

    image = ExtendedImageField(required=False, allow_null=True)
    is_new_client = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "phone",
            "image",
            "address",
            "role",
            "status",
            "last_active_at",
            "date_joined",
            "is_new_client",
        )
        read_only_fields = ("id", "role", "status", "last_active_at", "date_joined", "is_new_client")

    def get_is_new_client(self, obj):
        # A new client is someone who hasn't completed any bookings yet
        # If you prefer to check if they have NO bookings at all:
        return not obj.bookings.exists()"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Done")
else:
    print("Block not found!")
