angular.module('MarketIndex', ['ngRoute', 'cgBusy', 'ui.bootstrap'])

.controller('MainController', function($scope, $route, $routeParams, $location) {
	$scope.$route = $route;
	$scope.$location = $location;
	$scope.$routeParams = $routeParams;
})
.config(function($routeProvider, $locationProvider) {
	$routeProvider
		.when('/', {
			templateUrl: 'views/index.html',
			controller: IndexController,
		}).when('/kline', {
			templateUrl: 'views/kline.html',
			controller: KlineController,
		}).when('/trade-table', {
			templateUrl: 'views/trade_table.html',
			controller: TradeTableController,
		});
});
