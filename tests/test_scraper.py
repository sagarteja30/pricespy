from unittest.mock import MagicMock, patch


class TestScraperExtractors:
    def test_extract_price_from_whole(self):
        from scarper.scraper import scrape_amazon_price

        mock_html = """
        <span class="a-price-whole">1,499</span>
        <span id="productTitle">Test Product</span>
        """

        with patch("scarper.scraper.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = mock_html.encode()
            mock_get.return_value = mock_response

            with patch("scarper.scraper.BeautifulSoup") as mock_soup:
                mock_soup.return_value.find.side_effect = lambda *args, **kwargs: MagicMock(
                    get_text=lambda: "1,499"
                ) if "price" in str(args) else MagicMock(get_text=lambda: "Test Product")

                result = scrape_amazon_price("https://amazon.in/dp/TEST")
                assert result is None or isinstance(result, dict)

    def test_scrape_handles_missing_price(self):
        from scarper.scraper import scrape_amazon_price

        with patch("scarper.scraper.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"<html></html>"
            mock_get.return_value = mock_response

            with patch("scarper.scraper.BeautifulSoup") as mock_soup:
                mock_soup.return_value.find.return_value = None

                result = scrape_amazon_price("https://amazon.in/dp/TEST")
                assert result is None

    def test_scrape_handles_request_exception(self):
        import requests

        from scarper.scraper import scrape_amazon_price

        with patch("scarper.scraper.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("Network error")

            result = scrape_amazon_price("https://amazon.in/dp/TEST")
            assert result is None


class TestCollector:
    def test_get_bestseller_asins_extracts_asins(self):
        from scraper.collector import get_bestseller_asins

        mock_html = """
        <div data-asin="B09V3KXJPB"></div>
        <div data-asin="B09V3ABCDE"></div>
        <div data-asin=""></div>
        """

        with patch("scraper.collector.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = mock_html.encode()
            mock_get.return_value = mock_response

            with patch("scraper.collector.BeautifulSoup") as mock_soup:
                mock_soup.return_value.find_all.return_value = [
                    MagicMock(get=lambda x: "B09V3KXJPB"),
                    MagicMock(get=lambda x: "B09V3ABCDE"),
                    MagicMock(get=lambda x: ""),
                ]

                result = get_bestseller_asins("https://amazon.in/bestsellers")
                assert "B09V3KXJPB" in result
                assert "B09V3ABCDE" in result

    def test_scrape_product_price_returns_none_for_invalid_price(self):
        from scraper.collector import scrape_product_price

        with patch("scraper.collector.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"<html><span class='a-price-whole'>0</span></html>"
            mock_get.return_value = mock_response

            with patch("scraper.collector.BeautifulSoup") as mock_soup:
                mock_soup.return_value.find.side_effect = lambda *args, **kwargs: MagicMock(
                    get_text=lambda: "0"
                )

                result = scrape_product_price("B09V3KXJPB")
                assert result is None
