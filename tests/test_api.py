from backend.main import extract_asin, predict


class TestExtractASIN:
    def test_dp_format(self):
        url = "https://www.amazon.in/dp/B09V3KXJPB"
        assert extract_asin(url) == "B09V3KXJPB"

    def test_gp_product_format(self):
        url = "https://www.amazon.in/gp/product/B09V3KXJPB"
        assert extract_asin(url) == "B09V3KXJPB"

    def test_gp_aw_d_format(self):
        url = "https://www.amazon.in/gp/aw/d/B09V3KXJPB"
        assert extract_asin(url) == "B09V3KXJPB"

    def test_invalid_url(self):
        url = "https://example.com/product/123"
        assert extract_asin(url) is None

    def test_flipkart_url(self):
        url = "https://www.flipkart.com/product/p/abc123"
        assert extract_asin(url) is None


class TestPredict:
    def test_predict_with_low_data(self, sample_url):
        result = predict(sample_url, 1500.0)
        assert "recommendation" in result
        assert result["recommendation"] == "TRACKING"
        assert result["days_tracked"] == 1

    def test_predict_with_sufficient_data(self, sample_url, sample_prices, mock_db):
        mock_cursor = mock_db.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [(p,) for p in sample_prices]

        result = predict(sample_url, 1500.0)
        assert "recommendation" in result
        assert "confidence" in result
        assert "reason" in result
        assert result["days_tracked"] == len(sample_prices) + 1

    def test_predict_buy_now_when_price_rising(self, sample_url, mock_db):
        prices = [1000, 1100, 1200, 1300, 1400]
        mock_cursor = mock_db.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [(p,) for p in prices]

        result = predict(sample_url, 1450.0)
        assert result["recommendation"] in ["BUY NOW", "WAIT"]

    def test_predict_at_low_price(self, sample_url, mock_db):
        prices = [1500.0, 1600.0, 1700.0, 1800.0, 1900.0]
        mock_cursor = mock_db.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [(p,) for p in prices]

        result = predict(sample_url, 1550.0)
        assert "recommendation" in result
        assert result["best_price_30d"] == 1500

    def test_predict_result_structure(self, sample_url):
        result = predict(sample_url, 1500.0)
        expected_keys = [
            "predicted_price",
            "price_change",
            "pct_change",
            "recommendation",
            "reason",
            "confidence",
            "best_price_30d",
            "worst_price_30d",
            "days_tracked",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            assert "<html" in response.text.lower() or "<!doctype" in response.text.lower()
        else:
            data = response.json()
            assert "message" in data


class TestPredictionEndpoint:
    def test_predict_valid_request(self, client, sample_url, mock_db):
        payload = {
            "url": sample_url,
            "current_price": 1500.0,
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "recommendation" in data

    def test_predict_with_user_id(self, client, sample_url, mock_db):
        payload = {
            "url": sample_url,
            "current_price": 1500.0,
            "user_id": "test-user-123",
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 200

    def test_predict_invalid_url(self, client):
        payload = {
            "url": "https://invalid-site.com/product",
            "current_price": 1500.0,
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 422

    def test_predict_invalid_price(self, client, sample_url):
        payload = {
            "url": sample_url,
            "current_price": -100.0,
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 422

    def test_predict_missing_url(self, client):
        payload = {
            "current_price": 1500.0,
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 422

    def test_predict_missing_price(self, client, sample_url):
        payload = {
            "url": sample_url,
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 422
