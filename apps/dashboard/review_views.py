from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.booking.models import ShopReview
from apps.core.access import require_access_shop
from apps.core.permissions import IsShopStaff
from apps.core.responses import success_response
from apps.shop.models import Shop


class AdminReviewListAPIView(APIView):
    """GET: List reviews for a shop or a specific staff member."""

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_access_shop(request.user, shop.id)
        barber_id = request.query_params.get("barber_id")

        reviews = ShopReview.objects.filter(shop=shop)

        if barber_id:
            reviews = reviews.filter(booking__appointments__barber_id=barber_id).distinct()

        # Get overall stats
        stats = reviews.aggregate(average=Avg("rating"), total_reviews=Count("id"))

        # Rating distribution
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        rating_counts = reviews.values("rating").annotate(count=Count("id"))
        for rc in rating_counts:
            if rc["rating"] in distribution:
                distribution[rc["rating"]] = rc["count"]

        # Format reviews list
        reviews_data = []
        for review in reviews:
            reviews_data.append(
                {
                    "id": review.id,
                    "rating": review.rating,
                    "comment": review.comment,
                    "customer_name": review.customer.full_name or review.customer.username,
                    "customer_avatar": request.build_absolute_uri(review.customer.image.url)
                    if review.customer.image
                    else None,
                    "date": review.created_at.strftime("%d %b %Y"),
                }
            )

        data = {
            "summary": {
                "average_rating": round(stats["average"] or 0, 1),
                "total_reviews": stats["total_reviews"],
                "distribution": distribution,
            },
            "reviews": reviews_data,
        }

        return success_response(details="Reviews retrieved", code="REVIEWS_RETRIEVED", data=data)
