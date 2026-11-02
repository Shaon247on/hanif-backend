import sys

filepath = 'apps/barber/serializers.py'
with open(filepath, 'r') as f:
    content = f.read()

old_block = """        email = validated_data.pop("email")
        phone = validated_data.pop("phone", "")
        image = validated_data.pop("image", None)
        service_ids = validated_data.pop("services", [])

        user, created = User.objects.get_or_create(email=email)
        user.full_name = name
        user.phone = phone
        if image:
            user.image = image
        user.set_unique_username()
        if created:
            user.set_unusable_password()
        user.save()"""

new_block = """        email = validated_data.pop("email")
        phone = validated_data.pop("phone", "")
        image = validated_data.pop("image", None)
        service_ids = validated_data.pop("services", [])

        user = User.objects.filter(email=email).first()
        created = False
        if not user:
            user = User(email=email)
            user.set_unique_username()
            user.set_unusable_password()
            created = True

        user.full_name = name
        user.phone = phone
        if image:
            user.image = image
        # In case an old user somehow lacks a username
        if not user.username:
            user.set_unique_username()
        user.save()"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Done")
else:
    print("Block not found!")
