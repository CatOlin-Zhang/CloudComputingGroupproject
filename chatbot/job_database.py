# job_database.py
import openpyxl
import sqlite3
import pandas as pd
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

DB_NAME = 'jobs.db'


def init_database():
    """初始化数据库表结构，并在每次启动时清空旧数据"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    create_table_sql = '''
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        update_date TEXT,
        batch TEXT,
        company_name TEXT,
        company_type TEXT,
        industry TEXT,
        city TEXT,
        position_title TEXT,
        deadline TEXT,
        announcement_link TEXT,
        application_link TEXT,
        target_audience TEXT,
        education_req TEXT,
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    '''

    try:
        # 1. 创建表（如果不存在）
        cursor.execute(create_table_sql)

        # 2. 清空表中所有旧数据，确保每次运行都是干净的
        cursor.execute("DELETE FROM jobs")
        logger.info("Database table 'jobs' initialized and CLEARED for fresh import.")

        conn.commit()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e
    finally:
        conn.close()



def load_jobs_from_excel(excel_path: str) -> int:
    """
    读取 Excel 并导入数据库。
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    logger.info(f"Start loading jobs from {excel_path}...")

    conn = None  # 初始化 conn 为 None，防止未定义错误
    try:
        df = pd.read_excel(excel_path)

        column_mapping = {
            '岗位更新日期': 'update_date',
            '批次': 'batch',
            '企业名称': 'company_name',
            '企业类型': 'company_type',
            '行业': 'industry',
            '工作城市': 'city',
            '岗位': 'position_title',
            '截止时间': 'deadline',
            '公告链接': 'announcement_link',
            '网申入口': 'application_link',
            '招聘对象': 'target_audience',
            '学历': 'education_req',
            '备注': 'remarks'
        }

        # 检查并重命名列
        available_cols = {k: v for k, v in column_mapping.items() if k in df.columns}
        missing = set(column_mapping.keys()) - set(available_cols.keys())
        if missing:
            logger.warning(f"Missing columns in Excel: {missing}. Proceeding with available columns.")

        df.rename(columns=available_cols, inplace=True)
        target_columns = list(available_cols.values())

        # 确保只处理目标列
        df = df[target_columns]

        # --- 数据清洗 ---
        for col in target_columns:
            # 转为字符串，去除空格，处理 nan
            df[col] = df[col].apply(lambda x: str(x).strip() if pd.notnull(x) and str(x).strip() != 'nan' else None)

        # 去重
        df.drop_duplicates(subset=['company_name', 'position_title', 'deadline'], keep='last', inplace=True)

        logger.info(f"Preprocessing done. {len(df)} valid records found.")

        # --- 存入数据库 ---
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cols_str = ", ".join(target_columns)
        placeholders = ", ".join(["?" for _ in target_columns])
        insert_sql = f'INSERT INTO jobs ({cols_str}) VALUES ({placeholders})'

        data_tuples = [tuple(x) for x in df.to_numpy()]

        cursor.executemany(insert_sql, data_tuples)
        conn.commit()

        inserted_count = cursor.rowcount
        logger.info(f"Successfully inserted {inserted_count} jobs into database.")

        return inserted_count

    except Exception as e:
        logger.error(f"Error loading jobs from Excel: {e}")
        raise e
    finally:
        # 安全关闭连接：只有当 conn 成功创建时才关闭
        if conn:
            conn.close()
            logger.debug("Database connection closed.")


def search_jobs(keywords: List[str], city: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """搜索职位"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    conditions = []
    params = []

    # 关键词匹配 (岗位、行业、备注)
    if keywords:
        keyword_conditions = []
        for kw in keywords:
            # 使用 OR 连接不同字段的匹配
            keyword_conditions.append("(position_title LIKE ? OR industry LIKE ? OR remarks LIKE ?)")
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        conditions.append(" OR ".join(keyword_conditions))

    # 城市过滤
    if city:
        conditions.append("city LIKE ?")
        params.append(f"%{city}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
    SELECT * FROM jobs 
    WHERE {where_clause}
    ORDER BY id DESC
    LIMIT ?
    """
    params.append(limit)

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        logger.info(f"Search found {len(results)} jobs.")
        return results
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        return []
    finally:
        conn.close()


# 在 job_database.py 末尾添加

def get_all_jobs_as_text() -> str:
    """
    获取数据库中所有职位，格式化为文本字符串，供 AI 参考。
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # 查询所有字段
        cursor.execute("SELECT company_name, position_title, city, education_req, deadline, application_link FROM jobs")
        rows = cursor.fetchall()

        if not rows:
            return "目前数据库中没有可用的职位信息。"

        result_text = "以下是当前可用的职位列表：\n\n"
        for i, row in enumerate(rows, 1):
            # row: (company, position, city, edu, deadline, link)
            # 处理可能的 None 值
            company = row[0] or "未知公司"
            position = row[1] or "未知职位"
            city = row[2] or "不限"
            edu = row[3] or "不限"
            deadline = row[4] or "长期有效"
            link = row[5] or "#"

            result_text += f"{i}. 【{position}】 @ {company}\n"
            result_text += f"   城市: {city} | 学历: {edu}\n"
            result_text += f"   截止: {deadline}\n"
            result_text += f"   申请: {link}\n\n"

        return result_text

    except Exception as e:
        logging.error(f"Error fetching jobs for AI: {e}")
        return "暂时无法获取职位列表。"
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_database()
