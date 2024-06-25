import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from recipes.models import (
    AmountOfIngredient,
    Ingredient,
    IngredientInRecipe,
    Recipe,
    Tag,
    TagInRecipe,
)
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated
from rest_framework.validators import UniqueValidator

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)


class UserAvatarSerializer(UserSerializer):
    avatar = Base64ImageField(required=True, allow_null=False)

    class Meta:
        model = User
        fields = ('avatar',)


class UserMeSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )

    def to_representation(self, instance):
        request = self.context.get('request')
        if request.user.is_authenticated:
            return super().to_representation(instance)
        raise NotAuthenticated


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        help_text='Leave empty if no change needed',
        style={'input_type': 'password', 'placeholder': 'Password'},
    )
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())],
    )

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password',
        )

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Ingredient


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Tag


#####################################
# ####### new code from here ########
#####################################


class RecipeMetaSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )
        model = Recipe


class TagsInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=False,
    )

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')
        read_only_fields = ('name', 'slug')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        many=False,
        source='ingredient.id',
    )
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit',
    )

    class Meta:
        model = AmountOfIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeCreateSerializer(RecipeMetaSerializer):
    author = UserMeSerializer(read_only=True)
    image = Base64ImageField(required=True, allow_null=False)
    ingredients = IngredientInRecipeSerializer(many=True, required=True)
    tags = TagsInRecipeSerializer(many=True)

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError
        return value

    def to_internal_value(self, data):
        tags = data.pop('tags')
        data['tags'] = [{'id': tag} for tag in tags]
        return super().to_internal_value(data)

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        request = self.context.get('request')

        recipe = Recipe.objects.create(author=request.user, **validated_data)
        recipe.save()

        for tag in tags:
            current_tag, status = Tag.objects.get_or_create(id=tag['id'].pk)
            TagInRecipe.objects.create(
                tag=current_tag,
                recipe=recipe,
            )

        for ingredient in ingredients:
            current_ingredient, status = (
                AmountOfIngredient.objects.get_or_create(
                    ingredient=ingredient['ingredient']['id'],
                    amount=ingredient['amount'],
                )
            )
            IngredientInRecipe.objects.create(
                amount_of_ingredient=current_ingredient,
                recipe=recipe,
            )
        return recipe


class UserReadSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )


class RecipeRetrieveSerializer(RecipeCreateSerializer):
    author = UserReadSerializer(read_only=True)


class RecipeUpdateSerializer(RecipeCreateSerializer):
    image = Base64ImageField(required=False, allow_null=False)
