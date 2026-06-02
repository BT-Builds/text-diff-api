# Text Diff API

Compare two texts and generate unified diffs for audit trails, CMS versioning, and code review integrations.

## Endpoints

### `GET /health`
Health check endpoint.

### `POST /compare`
Compare two texts and return unified diff.

**Request Body:**
```json
{
  "text1": "Original text here",
  "text2": "Modified text",
  "context": 3,
  "ignore_whitespace": false,
  "ignore_case": false
}
```

**Response:**
```json
{
  "diff": "--- text1\n+++ text2\n@@ -1,1 +1,1 @@\n-original\n+modified",
  "changes": 2,
  "added_lines": 1,
  "removed_lines": 1,
  "similarity": 50.0
}
```

## Examples

```bash
curl -X POST https://text-diff-api.vercel.app/compare \
  -H "Content-Type: application/json" \
  -d '{"text1": "Hello World", "text2": "Hello Beautiful World"}'
```

## Pricing

- Free: 100 requests/month
- Pro: $19/month - 50k requests
- Business: $49/month - 250k requests

List on RapidAPI for passive income.
