import os
import sys
import logging
import ipaddress
from datetime import datetime
from typing import Any, cast

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

from db_utils import get_db_connection

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def _extract_client_ip():
    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    client_ip = raw_ip.split(",")[0].strip()
    return client_ip


def _anonymize_ip(ip_str):
    if not ip_str:
        return "0.0.0.0"

    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return "0.0.0.0"

    if isinstance(ip_obj, ipaddress.IPv4Address):
        octets = ip_str.split(".")
        if len(octets) == 4:
            octets[-1] = "0"
            return ".".join(octets)
        return "0.0.0.0"

    full_mask = (1 << 128) - 1
    lower_80_mask = (1 << 80) - 1
    anonymized_int = int(ip_obj) & (full_mask ^ lower_80_mask)
    return str(ipaddress.IPv6Address(anonymized_int))


def _fetch_geo(ip_str):
    if not ip_str:
        return {}

    url = f"http://ip-api.com/json/{ip_str}?fields=status,country,countryCode,regionName,city,lat,lon"
    try:
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return {}
        return {
            "country": data.get("country"),
            "country_code": data.get("countryCode"),
            "region": data.get("regionName"),
            "city": data.get("city"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
        }
    except Exception as e:
        logger.warning(f"IP 地理定位失败: {e}")
        return {}


def _empty_map_payload():
    return {
        "success": True,
        "total_visitors": 0,
        "countries": {},
        "recent": [],
    }


@app.route("/api/visitor", methods=["POST"])
def save_visitor():
    data = request.get_json(silent=True) or {}
    page_path = data.get("page") if isinstance(data, dict) else None
    if not isinstance(page_path, str) or not page_path.strip():
        page_path = "/"
    page_path = page_path.strip()[:500]

    user_agent = request.headers.get("User-Agent")
    ip_raw = _extract_client_ip()
    ip_anonymized = _anonymize_ip(ip_raw)

    conn = get_db_connection()
    if not conn:
        logger.warning("数据库不可用，跳过访客记录")
        return jsonify({"success": True}), 200

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM visitor_logs
            WHERE ip_anonymized = %s
              AND page_path = %s
              AND created_at >= NOW() - INTERVAL '30 minutes'
            LIMIT 1
            """,
            (ip_anonymized, page_path),
        )
        exists = cursor.fetchone()
        if exists:
            cursor.close()
            conn.close()
            return jsonify({"success": True}), 200

        geo = _fetch_geo(ip_raw)

        cursor.execute(
            """
            INSERT INTO visitor_logs (
                ip_anonymized, country, country_code, city, region,
                lat, lon, page_path, user_agent, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                ip_anonymized,
                geo.get("country"),
                geo.get("country_code"),
                geo.get("city"),
                geo.get("region"),
                geo.get("lat"),
                geo.get("lon"),
                page_path,
                user_agent,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True}), 200

    except Exception as e:
        logger.error(f"保存访客记录失败: {e}")
        if conn:
            conn.close()
        return jsonify({"success": True}), 200


@app.route("/api/visitor", methods=["GET"])
def get_visitor_map():
    since = request.args.get("since")
    since_dt = None

    if since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "since 参数格式错误，需为 YYYY-MM-DD"}), 400

    conn = get_db_connection()
    if not conn:
        logger.warning("数据库不可用，返回空访客数据")
        return jsonify(_empty_map_payload()), 200

    try:
        cursor = conn.cursor()

        where_sql = ""
        params = []
        if since_dt:
            where_sql = "WHERE created_at >= %s"
            params.append(since_dt)

        cursor.execute(
            f"""
            SELECT COUNT(DISTINCT ip_anonymized) AS total
            FROM visitor_logs
            {where_sql}
            """,
            tuple(params),
        )
        total_row = cast(dict[str, Any] | None, cursor.fetchone()) or {"total": 0}
        total_visitors = total_row.get("total", 0)

        cursor.execute(
            f"""
            SELECT
                COALESCE(country_code, 'UN') AS country_code,
                COALESCE(MAX(country), 'Unknown') AS country_name,
                COUNT(*) AS count
            FROM visitor_logs
            {where_sql}
            GROUP BY COALESCE(country_code, 'UN')
            ORDER BY count DESC
            """,
            tuple(params),
        )
        country_rows = cast(list[dict[str, Any]], cursor.fetchall())

        cursor.execute(
            f"""
            SELECT country_code, country_name, city, lat, lon, city_count
            FROM (
                SELECT
                    COALESCE(country_code, 'UN') AS country_code,
                    COALESCE(MAX(country), 'Unknown') AS country_name,
                    COALESCE(city, 'Unknown') AS city,
                    MAX(lat) AS lat,
                    MAX(lon) AS lon,
                    COUNT(*) AS city_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(country_code, 'UN')
                        ORDER BY COUNT(*) DESC
                    ) AS rn
                FROM visitor_logs
                {where_sql}
                GROUP BY COALESCE(country_code, 'UN'), COALESCE(city, 'Unknown')
            ) t
            WHERE rn <= 5
            ORDER BY country_code, city_count DESC
            """,
            tuple(params),
        )
        city_rows = cast(list[dict[str, Any]], cursor.fetchall())

        cursor.execute(
            f"""
            SELECT
                COALESCE(country_code, 'UN') AS country,
                COALESCE(city, 'Unknown') AS city,
                COALESCE(page_path, '/') AS page,
                created_at
            FROM visitor_logs
            {where_sql}
            ORDER BY created_at DESC
            LIMIT 10
            """,
            tuple(params),
        )
        recent_rows = cast(list[dict[str, Any]], cursor.fetchall())

        cursor.close()
        conn.close()

        countries = {}
        for row in country_rows:
            code = row["country_code"]
            countries[code] = {
                "name": row["country_name"],
                "count": row["count"],
                "cities": [],
            }

        for row in city_rows:
            code = row["country_code"]
            if code not in countries:
                countries[code] = {
                    "name": row["country_name"],
                    "count": 0,
                    "cities": [],
                }
            countries[code]["cities"].append(
                {
                    "name": row["city"],
                    "lat": float(row["lat"]) if row["lat"] is not None else None,
                    "lon": float(row["lon"]) if row["lon"] is not None else None,
                    "count": row["city_count"],
                }
            )

        recent = []
        for row in recent_rows:
            recent.append(
                {
                    "country": row["country"],
                    "city": row["city"],
                    "page": row["page"],
                    "time": row["created_at"].isoformat(),
                }
            )

        return jsonify(
            {
                "success": True,
                "total_visitors": total_visitors,
                "countries": countries,
                "recent": recent,
            }
        ), 200

    except Exception as e:
        logger.error(f"查询访客聚合数据失败: {e}")
        if conn:
            conn.close()
        return jsonify(_empty_map_payload()), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
