# mcp_server_weather.py
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import logging

# Configure logging for the server
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "mcp-gemini-chat-app/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Requesting NWS API: {url}")
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            logger.info(f"NWS API request successful: {url}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"NWS API request failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error during NWS API request: {e}")
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature.get("properties", {})
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Certainty: {props.get('certainty', 'Unknown')}
Urgency: {props.get('urgency', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY).
    """
    logger.info(f"Executing get_alerts for state: {state}")
    if not isinstance(state, str) or len(state) != 2:
        logger.warning(f"Invalid state code received: {state}")
        return "Invalid state code. Please provide a two-letter US state code (e.g., CA, NY)."

    url = f"{NWS_API_BASE}/alerts/active/area/{state.upper()}"
    data = await make_nws_request(url)

    if data is None:
        return "Unable to fetch alerts due to an API error."
    if "features" not in data or not data["features"]:
        return f"No active weather alerts found for {state.upper()}."

    alerts = [format_alert(feature) for feature in data["features"]]
    logger.info(f"Found {len(alerts)} alerts for {state.upper()}")
    return "\n---\n".join(alerts) if alerts else f"No active weather alerts for {state.upper()}."


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a specific latitude and longitude.

    Args:
        latitude: Latitude of the location (e.g., 38.8951).
        longitude: Longitude of the location (e.g., -77.0364).
    """
    logger.info(
        f"Executing get_forecast for lat: {latitude}, lon: {longitude}")
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return "Invalid coordinates. Latitude and longitude must be numbers."

    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data or "properties" not in points_data or "forecast" not in points_data["properties"]:
        return "Unable to fetch forecast grid data for this location. Please ensure coordinates are within the US."

    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data or "properties" not in forecast_data or "periods" not in forecast_data["properties"]:
        return "Unable to fetch detailed forecast for this location."

    periods = forecast_data["properties"]["periods"]
    if not periods:
        return "No forecast periods available for this location."

    forecasts = []
    for period in periods[:5]:  # Get next 5 periods
        forecast = f"""
{period.get('name', 'Unknown Period')}:
Temperature: {period.get('temperature', 'N/A')}°{period.get('temperatureUnit', 'N/A')}
Wind: {period.get('windSpeed', 'N/A')} {period.get('windDirection', 'N/A')}
Forecast: {period.get('detailedForecast', 'No detailed forecast available.')}
"""
        forecasts.append(forecast)

    logger.info(f"Generated forecast for {latitude}, {longitude}")
    return "\n---\n".join(forecasts)

if __name__ == "__main__":
    logger.info("Starting MCP weather server...")
    mcp.run(transport='stdio')
    logger.info("MCP weather server stopped.")
