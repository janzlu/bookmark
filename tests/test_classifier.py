#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch
from bookmark_cleaner.classifier import BookmarkClassifier


def test_classify_without_api_key():
    classifier = BookmarkClassifier(api_key="", base_url="http://mock", model_name="test")
    batch = [{"id": "1", "name": "Test", "url": "http://test.com"}]
    res = classifier.classify_single_batch(batch)
    assert res == {"1": "其他/待整理"}


def test_classify_single_batch_success():
    classifier = BookmarkClassifier(
        api_key="mock-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini"
    )

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"1": "技术研发/AI与大模型", "2": "效率工具/常用服务"})
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    classifier._client = mock_client

    batch = [
        {"id": "1", "name": "Claude", "url": "https://claude.ai"},
        {"id": "2", "name": "Notion", "url": "https://notion.so"}
    ]
    res = classifier.classify_single_batch(batch)
    assert res == {"1": "技术研发/AI与大模型", "2": "效率工具/常用服务"}


def test_classify_batch_wrapped_format():
    classifier = BookmarkClassifier(
        api_key="mock-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini"
    )

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "bookmarks": {
            "10": "产品设计/灵感素材"
        }
    })
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    classifier._client = mock_client

    batch = [{"id": "10", "name": "Dribbble", "url": "https://dribbble.com"}]
    res = classifier.classify_single_batch(batch)
    assert res == {"10": "产品设计/灵感素材"}


def test_classify_batch_exception_fallback():
    classifier = BookmarkClassifier(
        api_key="mock-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini"
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Network error")
    classifier._client = mock_client

    batch = [{"id": "99", "name": "Err", "url": "http://err.com"}]
    res = classifier.classify_single_batch(batch, max_retries=0)
    assert res == {"99": "其他/待整理"}


def test_classify_batch_thinking_and_markdown():
    classifier = BookmarkClassifier(
        api_key="mock-key",
        base_url="https://api.minimax.chat/v1",
        model_name="MiniMax-M2.7"
    )

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        "<think>模型思考过程：将 GitHub 归类到技术研发</think>\n\n"
        "```json\n"
        '{"1": "技术研发/编程开发"}\n'
        "```"
    )
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    classifier._client = mock_client

    batch = [{"id": "1", "name": "GitHub", "url": "https://github.com"}]
    res = classifier.classify_single_batch(batch)
    assert res == {"1": "技术研发/编程开发"}
