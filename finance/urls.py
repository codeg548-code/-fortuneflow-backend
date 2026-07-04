from django.urls import path, include
from . import views
from .api import api_router
from .auth_api import LoginAPIView, LogoutAPIView, MeAPIView, SignupAPIView

urlpatterns = [
    path('accueil', views.accueil_view, name='accueil'), 
    path('', views.login_view, name='login'), 
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'), 
    path('signup/<int:ref>/', views.signup_view, name='signup_with_ref'), 
    path('logout/', views.logout_view, name='logout'),
    path('packs/', views.pack_view, name='packs'), 
    path('buy-pack/', views.buypack_view, name='buy-pack-global'), 
    path('buy-pack/<int:pack_id>/', views.buypack_view, name='buy-pack'),
    path('depot/', views.depot_view, name='depot'), 
    path('retrait/', views.retrait_view, name='retrait'), 
    path('mes-depots/', views.mesdepots_view, name='mes-depots'),
    path('mes-retraits/', views.mesretraits_view, name='mes-retraits'), 
    path('mes-packs/', views.mespacks_view, name='mes-packs'), 
    path('compte/', views.compte_view, name='compte'),
    path('parrainage/', views.parrainage_view, name='parrainage'),
    path('admin/dashboard/', views.admin_dashboard_view, name='admin-dashboard'),
    path('admin/users/', views.user_view, name='admin-users'), 
    path('admin/valider-depot/', views.valdep_view, name='valider-depot'), 
    path('admin/valider-depot/action/<int:codeDepot>/', views.valider_depot_action, name='valider_depot_action'),
    path('admin/valider-retrait/', views.valretrait_view, name='valider-retrait'),
    path('admin/valider-retrait/action/<int:codeRetrait>/', views.valider_retrait_action, name='valider_retrait_action'), # valRetrait_controller.php
    path('admin/withdrawal-suspensions/', views.withdrawal_suspensions_view, name='withdrawal-suspensions'),
    path('politique/', views.politique_controller, name='politique'), 
    path('api/auth/login/', LoginAPIView.as_view(), name='api-login'),
    path('api/auth/signup/', SignupAPIView.as_view(), name='api-signup'),
    path('api/auth/signup/<int:ref>/', SignupAPIView.as_view(), name='api-signup-ref'),
    path('api/auth/logout/', LogoutAPIView.as_view(), name='api-logout'),
    path('api/auth/me/', MeAPIView.as_view(), name='api-me'),
    path('api/', include(api_router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
