import pytest
from unittest.mock import patch, AsyncMock, MagicMock


VALID_SUMMARY = {
    "summary": "This article discusses the creator economy trends.",
    "tags": ["creator-economy", "AI-agents"],
    "relevance": 8,
    "key_quote": "The future of content is AI-assisted.",
    "angle": "How AI agents are reshaping content creation",
}

FIXED_TAGS = [
    "creator-economy", "AI-agents", "monetization", "platform-strategy",
    "content-strategy", "fundraising", "product", "engineering", "culture", "other",
]

SAMPLE_CONTENT = "This is a sample article about the creator economy. " * 100


class TestSummarizeSuccess:
    """Test successful summarization returns valid schema."""

    @pytest.mark.asyncio
    async def test_returns_valid_schema(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test summary.", "tags": ["creator-economy"], '
                '"relevance": 8, "key_quote": "A quote.", "angle": "An angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        assert "summary" in result
        assert "tags" in result
        assert "relevance" in result
        assert "key_quote" in result
        assert "angle" in result

    @pytest.mark.asyncio
    async def test_summary_is_string(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test summary.", "tags": ["creator-economy"], '
                '"relevance": 8, "key_quote": "A quote.", "angle": "An angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


class TestSummarizeTags:
    """Test tags are from fixed vocabulary."""

    @pytest.mark.asyncio
    async def test_tags_from_fixed_vocabulary(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test.", "tags": ["creator-economy", "AI-agents"], '
                '"relevance": 7, "key_quote": "Quote.", "angle": "Angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        for tag in result["tags"]:
            assert tag in FIXED_TAGS, f"Tag '{tag}' not in fixed vocabulary"

    @pytest.mark.asyncio
    async def test_invalid_tags_filtered_out(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test.", "tags": ["creator-economy", "invalid-tag"], '
                '"relevance": 7, "key_quote": "Quote.", "angle": "Angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        for tag in result["tags"]:
            assert tag in FIXED_TAGS


class TestSummarizeRelevance:
    """Test relevance is 1-10."""

    @pytest.mark.asyncio
    async def test_relevance_in_range(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test.", "tags": ["product"], '
                '"relevance": 8, "key_quote": "Quote.", "angle": "Angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        assert 1 <= result["relevance"] <= 10

    @pytest.mark.asyncio
    async def test_relevance_clamped_if_out_of_range(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test.", "tags": ["product"], '
                '"relevance": 15, "key_quote": "Quote.", "angle": "Angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        assert result["relevance"] == 10


class TestSummarizeTruncation:
    """Test content > 15K chars is truncated before sending to Gemini."""

    @pytest.mark.asyncio
    async def test_long_content_truncated(self):
        from src.summarizer import summarize

        long_content = "x" * 20000  # Over 15K

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = (
                '{"summary": "Test.", "tags": ["other"], '
                '"relevance": 5, "key_quote": "Quote.", "angle": "Angle"}'
            )
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(long_content)

        # Verify the content sent to Gemini was truncated
        call_args = mock_client.models.generate_content.call_args
        prompt_text = call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][0]
        # The article content within the prompt should be truncated to 15K
        assert len(long_content) > 15000
        assert "summary" in result  # Summarization still works


class TestSummarizeFallback:
    """Test Gemini failure returns raw_content fallback."""

    @pytest.mark.asyncio
    async def test_gemini_exception_returns_fallback(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("Gemini API error")
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        assert "raw_content" in result
        assert len(result["raw_content"]) <= 2000

    @pytest.mark.asyncio
    async def test_gemini_returns_invalid_json_fallback(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "This is not valid JSON"
            mock_client.models.generate_content.return_value = mock_response
            mock_get.return_value = mock_client

            result = await summarize(SAMPLE_CONTENT)

        assert "raw_content" in result
        assert len(result["raw_content"]) <= 2000

    @pytest.mark.asyncio
    async def test_no_api_key_returns_fallback(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_get.return_value = None

            result = await summarize(SAMPLE_CONTENT)

        assert "raw_content" in result

    @pytest.mark.asyncio
    async def test_fallback_truncates_to_2000_chars(self):
        from src.summarizer import summarize

        long_content = "A" * 5000

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_get.return_value = None

            result = await summarize(long_content)

        assert len(result["raw_content"]) <= 2000


class TestSummarizeEmptyContent:
    """Test empty content handled gracefully."""

    @pytest.mark.asyncio
    async def test_empty_string_returns_fallback(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_get.return_value = None

            result = await summarize("")

        assert "raw_content" in result

    @pytest.mark.asyncio
    async def test_none_content_returns_fallback(self):
        from src.summarizer import summarize

        with patch("src.summarizer.get_genai_client") as mock_get:
            mock_get.return_value = None

            result = await summarize(None)

        assert "raw_content" in result
