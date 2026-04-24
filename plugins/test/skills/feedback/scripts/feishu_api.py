#!/usr/bin/env python3
"""
飞书项目 Open API 工具

用于更新飞书项目工作项的受限字段（描述、报告人、经办人、业务线等）
这些字段可以通过飞书项目 Open API 直接更新

使用方法:
    python feishu_api.py --work_item_id 6755691869 --description "问题描述..." --reporter jinshichen --operator chenhao --business 商店

环境变量:
    FEISHU_PLUGIN_ID: 飞书项目插件 ID
    FEISHU_PLUGIN_SECRET: 飞书项目插件 Secret
    FEISHU_USER_KEY: 用户标识

参考文档:
    - 飞书项目 Open API: https://project.feishu.cn/b/helpcenter/1p8d7djs/5aueo3jr
"""

import os
import sys
import json
import argparse
import asyncio
import ssl
from typing import Optional, Dict, Any, List

# 检查 aiohttp 是否安装
try:
    import aiohttp
except ImportError:
    print("❌ 错误: 需要安装 aiohttp 库")
    print("   请运行: pip install aiohttp")
    sys.exit(1)


def decode_escape_sequences(text: str) -> str:
    """
    解码字符串中的转义序列（如 \\n -> 换行符）
    
    当从命令行传入包含 \\n 的字符串时，Python 会将其作为字面量字符串，
    需要手动转换为真正的换行符。
    
    Args:
        text: 可能包含转义序列的字符串
        
    Returns:
        解码后的字符串
    """
    if not text:
        return text
    
    # 手动替换常见的转义序列，避免使用 codecs.decode 导致中文字符编码问题
    # 注意：替换顺序很重要，先替换 \\r\\n，再替换单独的 \\n 和 \\r
    replacements = [
        ('\\r\\n', '\r\n'),  # Windows 换行
        ('\\n', '\n'),       # Unix 换行
        ('\\r', '\r'),       # Mac 换行
        ('\\t', '\t'),       # Tab
        ('\\\\', '\\'),      # 反斜杠（必须在最后，避免影响其他替换）
    ]
    
    result = text
    for escaped, actual in replacements:
        result = result.replace(escaped, actual)
    
    return result

# 全局缓存：飞书成员邮箱到 user_key 的映射
_feishu_email_to_userkey_cache: Dict[str, str] = {}
# 全局缓存：飞书成员姓名到 user_key 的映射（用于邮箱为空时的备用匹配）
_feishu_name_to_userkey_cache: Dict[str, str] = {}


class FeishuProjectAPI:
    """飞书项目 API 客户端"""
    """api 文档 https://project.feishu.cn/b/helpcenter/1p8d7djs/5kwry3yy"""
    # 项目配置
    PROJECT_KEY = "68ed0fb4eb01f908527bdb2f"  # TapTap 主站项目 ID
    SIMPLE_NAME = "pojq34"  # 项目简称
    
    # 业务线 ID 映射
    BUSINESS_MAP = {
        "商店": "68ed297f86ef93817f0876f9",
        "社区": "68ed297786ef93817f0876f8",
        "iOS": "68ed298505b48408402204ee",
        "小游戏": "68ed2971dc0557f33cdb00e4",
        "启动器": "68ed2993387637a94158d910",
        "PC": "6908b094f3749675989dc41d",
        "TapSDK": "69153f74ebf5b62fcd8a828e",
        "账号价值": "68ed29ad3bd92c08ac64d9a0",
        "服务端基建": "69153f5a719d070926be483f",
        "前端基建": "69153f667c2407e598e14c3f",
        "风控内审": "69153f7e7c2407e598e14c40",
        "测试基建": "69153f887c2407e598e14c41",
        "设计基建": "69153f927c2407e598e14c42",
    }
    
    # 用户 key 映射（用户名 -> user_key）
    # 数据来源: 飞书项目 API /open_api/{project_key}/teams/all + /open_api/user/query
    USER_MAP = {
        # === 测试负责人 ===
        "jinshichen": "7519012859116879900",  # 金诗晨 - 商店/社区 + iOS 社区版（接手 wangweidong 离职后的工作）
        "zhangtao": "7094479243123507203",     # 张涛 - 小游戏/TapSDK
        "zhouchunhui": "7540167756541427715",  # 周春晖 - 沙盒/云玩
        "liyafeng": "7308268753316298753",     # 李雅峰 - PC 启动器
        
        # === 研发负责人 ===
        # 商店/社区
        "chenhao1": "7519012859116896284",    # 陈昊 - Android
        "chenhao": "7519012859116896284",     # 陈昊 (别名)
        "cyh": "7094560275751305219",         # 陈一豪 - Server
        "chenyihao": "7094560275751305219",   # 陈一豪 (别名)
        "liufeng": "7519017242672037916",     # 刘峰 - Web
        
        # 小游戏
        "dingshuai": "7518970146577186820",   # 丁帅 - iOS (暂用黄帅佳的key，需确认)
        "huangshuaijia": "7518970146577186820",  # 黄帅佳 - Android
        
        # iOS 社区版
        "zhouxianli": "7518969208693178369",  # 周贤力 - iOS
        
        # TapSDK (线上问题统一指派给潘扬)
        "apollopy": "7095966022934609948",    # 潘扬 - 技术TL (TapSDK线上问题默认经办人)
        "panyang": "7095966022934609948",     # 潘扬 (别名)
        "lichao": "7101643523006431233",      # 李超 - 登录 (内部分配)
        "zhaojunjie": "7519007089134551068",  # 赵俊杰 - 实名 (内部分配)
        "ningjiachen": "7094560275751337987", # 宁佳晨 - Server (内部分配)
        "zhaoyang1": "7519017004930465794",   # 赵阳 - 客户端 (内部分配)
        
        # PC 启动器
        "nick": "7096367104131153948",        # 杨鹏博 - 技术TL
        "yangpengbo": "7096367104131153948",  # 杨鹏博 (别名)
        "uffy": "7097088207195684866",        # 温友强 - Server
        "wenyouqiang": "7097088207195684866", # 温友强 (别名)
        "liyong": "7094560958248386563",      # 李勇 - Server
        "lizhe01": "7098237527676567580",     # 李哲 - Server
        "shenyang": "7096395884669222914",    # 沈阳 - 客户端
        "huangzhenpeng": "7097104943018000385",  # 黄振鹏 - 客户端
        "xushengfeng": "7519005209889210369", # 许圣峰 - 客户端
        
        # 沙盒/云玩
        "luokun": "7518975537725931524",      # 罗鲲 - 沙盒游戏
    }
    
    def __init__(self, plugin_id: Optional[str] = None, plugin_secret: Optional[str] = None,
                 user_key: Optional[str] = None, auto_load_cache: bool = False):
        """
        初始化飞书项目 API 客户端
        
        Args:
            plugin_id: 飞书项目插件 ID，默认从环境变量 FEISHU_PLUGIN_ID 获取
            plugin_secret: 飞书项目插件 Secret，默认从环境变量 FEISHU_PLUGIN_SECRET 获取
            user_key: 用户标识，默认从环境变量 FEISHU_USER_KEY 获取
            auto_load_cache: 是否自动加载用户映射缓存（默认 False，按需加载）
        """
        self.plugin_id = plugin_id or os.getenv("FEISHU_PLUGIN_ID", "")
        self.plugin_secret = plugin_secret or os.getenv("FEISHU_PLUGIN_SECRET", "")
        self.user_key = user_key or os.getenv("FEISHU_USER_KEY", "")
        self._plugin_token = None
        self._cache_loaded = False
        
        # SSL 配置（跳过证书验证）
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # 如果启用自动加载缓存，在初始化时加载
        if auto_load_cache:
            # 注意：这里不能直接调用 async 方法，需要在外部调用 load_members_cache
            pass
        
    async def _get_plugin_token(self) -> str:
        """获取 plugin_token"""
        if self._plugin_token:
            return self._plugin_token
            
        url = "https://project.feishu.cn/open_api/authen/plugin_token"
        payload = {
            "plugin_id": self.plugin_id,
            "plugin_secret": self.plugin_secret
        }
        
        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                
                if data.get("error", {}).get("code") == 0:
                    self._plugin_token = data["data"]["token"]
                    return self._plugin_token
                else:
                    raise Exception(f"获取 plugin_token 失败: {data}")
    
    async def _request(self, method: str, path: str, body: Optional[Dict] = None, use_open_api: bool = False) -> Dict:
        """
        发送 API 请求
        
        Args:
            method: HTTP 方法
            path: API 路径
            body: 请求体
            use_open_api: 是否使用标准开放平台 API (open.feishu.cn)，否则使用项目 Open API (project.feishu.cn)
        """
        token = await self._get_plugin_token()
        
        # 根据路径判断使用哪个域名
        if path.startswith("/open-apis/"):
            # 标准开放平台 API
            url = f"https://open.feishu.cn{path}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        else:
            # 飞书项目 Open API
            url = f"https://project.feishu.cn{path}"
            headers = {
                "X-PLUGIN-TOKEN": token,
                "X-USER-KEY": self.user_key,
                "Content-Type": "application/json"
            }
        
        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            if method == "GET":
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method == "POST":
                async with session.post(url, headers=headers, json=body) as response:
                    return await response.json()
            elif method == "PUT":
                async with session.put(url, headers=headers, json=body) as response:
                    return await response.json()
            else:
                raise ValueError(f"不支持的 HTTP 方法: {method}")
    
    async def load_members_cache(self) -> Dict[str, str]:
        """
        加载飞书项目成员邮箱和姓名到 user_key 的映射缓存
        
        Returns:
            Dict[str, str]: 邮箱到 user_key 的映射
        """
        global _feishu_email_to_userkey_cache, _feishu_name_to_userkey_cache
        
        # 如果缓存已加载，直接返回
        if _feishu_email_to_userkey_cache:
            self._cache_loaded = True
            return _feishu_email_to_userkey_cache
        
        try:
            # 1. 获取所有团队成员的 user_keys
            path = f"/open_api/{self.PROJECT_KEY}/teams/all"
            data = await self._request("GET", path)
            
            if data.get("err_code") != 0:
                print(f"⚠️ 警告: 获取团队列表失败: {data.get('err_msg', data)}")
                return {}
            
            # 收集所有 user_keys
            all_user_keys = set()
            teams = data.get("data", [])
            for team in teams:
                user_keys = team.get("user_keys", [])
                all_user_keys.update(user_keys)
            
            if not all_user_keys:
                print("⚠️ 警告: 未找到团队成员")
                return {}
            
            print(f"📋 找到 {len(all_user_keys)} 个成员，正在查询详情...")
            
            # 2. 批量查询用户详情（每次最多 100 个）
            user_keys_list = list(all_user_keys)
            batch_size = 100
            
            for i in range(0, len(user_keys_list), batch_size):
                batch = user_keys_list[i:i + batch_size]
                path = "/open_api/user/query"
                body = {"user_keys": batch}
                data = await self._request("POST", path, body)
                
                if data.get("err_code") == 0:
                    users = data.get("data", [])
                    for user in users:
                        email = user.get("email", "").lower()
                        user_key = user.get("user_key")
                        name_cn = user.get("name_cn", "")
                        if user_key:
                            # 存储邮箱映射
                            if email:
                                _feishu_email_to_userkey_cache[email] = user_key
                            # 存储姓名映射（用于邮箱为空时的备用匹配）
                            if name_cn:
                                _feishu_name_to_userkey_cache[name_cn] = user_key
            
            self._cache_loaded = True
            print(f"✅ 成员映射加载完成: 邮箱 {len(_feishu_email_to_userkey_cache)} 个, 姓名 {len(_feishu_name_to_userkey_cache)} 个")
            return _feishu_email_to_userkey_cache
            
        except Exception as e:
            print(f"❌ 加载飞书成员列表失败: {e}")
            return {}
    
    def get_user_key_from_cache(self, email: str = "", name: str = "", username: str = "") -> str:
        """
        从缓存中查询飞书用户 Key
        
        优先级：邮箱 > 姓名 > 用户名（静态映射）
        
        Args:
            email: 用户邮箱
            name: 用户姓名（备用匹配）
            username: 用户名（回退到静态 USER_MAP）
            
        Returns:
            str: 飞书用户 Key，查询失败返回默认用户 Key
        """
        global _feishu_email_to_userkey_cache, _feishu_name_to_userkey_cache
        
        # 1. 通过邮箱匹配
        if email:
            email_lower = email.lower()
            if email_lower in _feishu_email_to_userkey_cache:
                return _feishu_email_to_userkey_cache[email_lower]
            
            # 尝试匹配 @xd.com 域名的邮箱
            if not email_lower.endswith("@xd.com") and "@" in email_lower:
                email_with_domain = f"{email_lower.split('@')[0]}@xd.com"
                if email_with_domain in _feishu_email_to_userkey_cache:
                    return _feishu_email_to_userkey_cache[email_with_domain]
        
        # 2. 通过姓名匹配（备用方案）
        if name:
            if name in _feishu_name_to_userkey_cache:
                return _feishu_name_to_userkey_cache[name]
            
            # 尝试匹配姓名中的部分（处理中英文组合名）
            name_parts = name.split()
            for part in name_parts:
                if part in _feishu_name_to_userkey_cache:
                    return _feishu_name_to_userkey_cache[part]
        
        # 3. 通过用户名匹配（回退到静态映射）
        if username:
            user_key = self.USER_MAP.get(username)
            if user_key:
                return user_key
        
        # 4. 如果都未找到，返回默认用户 Key
        if email or name or username:
            print(f"⚠️ 警告: 用户 '{name or username}' <{email}> 未找到对应飞书用户，使用默认用户")
        return self.user_key
    
    async def get_work_item(self, work_item_id: str) -> Dict:
        """
        获取工作项详情
        
        Args:
            work_item_id: 工作项 ID
            
        Returns:
            工作项详情
        """
        path = f"/open_api/{self.PROJECT_KEY}/work_item/issue/query"
        body = {"work_item_ids": [work_item_id]}
        
        result = await self._request("POST", path, body)
        if result.get("err_code") == 0:
            items = result.get("data", [])
            return items[0] if items else {}
        return result
    
    async def update_work_item(
        self,
        work_item_id: str,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        reporter: Optional[str] = None,
        operator: Optional[str] = None,
        business: Optional[str] = None,
        severity: Optional[str] = None,
        bug_classification: Optional[str] = None,
        issue_stage: Optional[str] = None,
    ) -> Dict:
        """
        更新工作项（支持受限字段）
        
        Args:
            work_item_id: 工作项 ID
            description: 描述内容（Markdown 格式）
            priority: 优先级 (P0/P1/P2/P3)
            reporter: 报告人用户名（会自动转换为 user_key）
            operator: 经办人用户名（会自动转换为 user_key）
            business: 业务线名称（会自动转换为业务线 ID）
            severity: 严重程度 (致命/严重/一般/轻微)
            bug_classification: Bug端分类 (iOS/Android/FE/Server)
            issue_stage: 发现阶段
            
        Returns:
            API 响应
        """
        path = f"/open_api/{self.PROJECT_KEY}/work_item/issue/{work_item_id}"
        
        update_fields = []
        
        # 优先级字段
        if priority:
            # 优先级需要转换为对象格式
            priority_obj = self._convert_priority_to_feishu_format(priority)
            update_fields.append({
                "field_key": "priority",
                "field_value": priority_obj
            })
        
        # 描述字段
        if description:
            update_fields.append({
                "field_alias": "description",
                "field_value": description
            })
            
        # 业务线字段
        if business:
            business_id = self.BUSINESS_MAP.get(business)
            if not business_id:
                print(f"⚠️ 警告: 业务线 '{business}' 不在可选列表中")
                print(f"   可选值: {', '.join(self.BUSINESS_MAP.keys())}")
            else:
                update_fields.append({
                    "field_alias": "business",
                    "field_value": business_id
                })
        
        # 严重程度字段（select 类型，需要转换为对象格式）
        if severity:
            severity_obj = self._convert_severity_to_feishu_format(severity)
            update_fields.append({
                "field_key": "severity",
                "field_value": severity_obj
            })
        
        # Bug端分类字段（select 类型，需要转换为对象格式）
        if bug_classification:
            classification_obj = self._convert_bug_classification_to_feishu_format(bug_classification)
            update_fields.append({
                "field_key": "bug_classification",
                "field_value": classification_obj
            })
        
        # 发现阶段字段（select 类型，需要转换为对象格式）
        if issue_stage:
            stage_obj = self._convert_issue_stage_to_feishu_format(issue_stage)
            update_fields.append({
                "field_key": "issue_stage",
                "field_value": stage_obj
            })
        
        # 角色字段（报告人和经办人）
        role_owners = []
        
        if reporter:
            # 优先从缓存查询，如果未找到则尝试静态映射
            reporter_key = self.get_user_key_from_cache(username=reporter)
            role_owners.append({
                "role": "reporter",
                "owners": [reporter_key]
            })
            
        if operator:
            # 优先从缓存查询，如果未找到则尝试静态映射
            operator_key = self.get_user_key_from_cache(username=operator)
            role_owners.append({
                "role": "operator",
                "owners": [operator_key]
            })
            
        if role_owners:
            update_fields.append({
                "field_key": "role_owners",
                "field_value": role_owners
            })
            
        if not update_fields:
            raise ValueError("至少需要提供一个要更新的字段")
            
        body = {"update_fields": update_fields}
        return await self._request("PUT", path, body)
    
    async def create_work_item(
        self,
        work_item_type: str = "Bugs",
        name: str = "",
        priority: Optional[str] = None,
        severity: Optional[str] = None,
        bug_classification: Optional[str] = None,
        issue_stage: Optional[str] = None,
        description: Optional[str] = None,
        business: Optional[str] = None,
        reporter: Optional[str] = None,
        operator: Optional[str] = None,
    ) -> Dict:
        """
        创建工作项（Bug/需求/任务等）
        
        Args:
            work_item_type: 工作项类型，默认为 "Bugs"
            name: 工作项标题
            priority: 优先级 (P0/P1/P2/P3)
            severity: 严重程度 (致命/严重/一般/轻微)
            bug_classification: Bug端分类 (iOS/Android/FE/Server)
            issue_stage: 发现阶段
            description: 描述内容（Markdown 格式）
            business: 业务线名称（会自动转换为业务线 ID）
            reporter: 报告人用户名（会自动转换为 user_key）
            operator: 经办人用户名（会自动转换为 user_key）
            
        Returns:
            API 响应，包含 work_item_id
        """
        # 使用飞书项目 Open API 创建工作项
        # 创建时只设置 name 字段，其他所有字段通过更新接口设置
        path = f"/open_api/{self.PROJECT_KEY}/work_item/create"
        
        field_value_pairs = []
        
        # 必填字段：名称（创建时只设置这一个字段）
        if name:
            field_value_pairs.append({
                "field_key": "name",
                "field_value": name
            })
        
        # 使用 work_item_type_key（参考 jira_feishu_migration.py 使用 "issue"）
        body = {
            "work_item_type_key": "issue",  # 使用 "issue" 而不是 "Bugs"
            "field_value_pairs": field_value_pairs
        }
        
        result = await self._request("POST", path, body)
        
        # 处理响应（参考 jira_feishu_migration.py）
        if result.get("err_code") == 0:
            # 飞书 API 可能直接返回 {"data": 工作项ID} 或 {"data": {"id": 工作项ID}}
            work_item_data = result.get("data")
            if isinstance(work_item_data, dict):
                work_item_id = work_item_data.get("id") or work_item_data.get("work_item_id")
            elif isinstance(work_item_data, (int, str)):
                # 直接返回整数 ID 或字符串 ID
                work_item_id = work_item_data
            else:
                work_item_id = None
            
            # 如果成功提取到 work_item_id，更新返回结果格式
            if work_item_id:
                result["work_item_id"] = work_item_id
                
                # 创建成功后，将所有其他字段通过更新接口设置
                needs_update = False
                update_kwargs = {}
                
                if priority:
                    needs_update = True
                    update_kwargs["priority"] = priority
                if description:
                    needs_update = True
                    update_kwargs["description"] = description
                if business:
                    needs_update = True
                    update_kwargs["business"] = business
                if reporter:
                    needs_update = True
                    update_kwargs["reporter"] = reporter
                if operator:
                    needs_update = True
                    update_kwargs["operator"] = operator
                if severity:
                    needs_update = True
                    update_kwargs["severity"] = severity
                if bug_classification:
                    needs_update = True
                    update_kwargs["bug_classification"] = bug_classification
                if issue_stage:
                    needs_update = True
                    update_kwargs["issue_stage"] = issue_stage
                
                # 如果有需要更新的字段，调用更新接口
                if needs_update:
                    try:
                        update_result = await self.update_work_item(
                            work_item_id=work_item_id,
                            **update_kwargs
                        )
                        if update_result.get("err_code") == 0:
                            print(f"✅ 字段 {', '.join(update_kwargs.keys())} 已更新")
                        else:
                            print(f"⚠️ 警告: 字段 {', '.join(update_kwargs.keys())} 更新失败: {update_result.get('err_msg', update_result)}")
                    except Exception as e:
                        print(f"⚠️ 警告: 更新字段时出错: {e}")
        
        return result
    
    def _convert_priority_to_feishu_format(self, priority: str) -> Dict[str, str]:
        """
        将优先级字符串转换为飞书 API 需要的对象格式
        
        Args:
            priority: 优先级字符串（P0/P1/P2/P3）
            
        Returns:
            Dict: 飞书优先级对象格式 {"label": "P1", "value": "1"}
        """
        priority_value_map = {
            "P0": "0",
            "P0.5": "1",
            "P1": "1",
            "P1.5": "2",
            "P2": "2",
            "P2.5": "2",
            "P3": "q4xi0i9dq",
        }
        value = priority_value_map.get(priority, "2")  # 默认 P2
        return {"label": priority, "value": value}
    
    def _convert_severity_to_feishu_format(self, severity: str) -> Dict[str, str]:
        """
        将严重程度字符串转换为飞书 API 需要的对象格式
        
        Args:
            severity: 严重程度字符串（致命/严重/一般/轻微）
            
        Returns:
            Dict: 飞书严重程度对象格式 {"label": "严重", "value": "2"}
        """
        severity_value_map = {
            "致命": "1",
            "严重": "2",
            "一般": "3",
            "轻微": "4",
        }
        value = severity_value_map.get(severity, "3")  # 默认一般
        return {"label": severity, "value": value}
    
    def _convert_bug_classification_to_feishu_format(self, bug_classification: str) -> Dict[str, str]:
        """
        将 Bug 端分类字符串转换为飞书 API 需要的对象格式
        
        Args:
            bug_classification: Bug 端分类字符串（iOS/Android/FE/Server）
            
        Returns:
            Dict: 飞书 Bug 端分类对象格式 {"label": "Android", "value": "android"}
        """
        classification_value_map = {
            "iOS": "ios",
            "Android": "android",
            "FE": "fe",
            "Server": "server",
        }
        value = classification_value_map.get(bug_classification, "android")  # 默认 Android
        return {"label": bug_classification, "value": value}
    
    def _convert_issue_stage_to_feishu_format(self, issue_stage: str) -> Dict[str, str]:
        """
        将发现阶段字符串转换为飞书 API 需要的对象格式
        
        Args:
            issue_stage: 发现阶段字符串（线上阶段/灰度阶段/回归测试等）
            
        Returns:
            Dict: 飞书发现阶段对象格式 {"label": "线上阶段", "value": "stage_online"}
        """
        stage_value_map = {
            "UI/UE/PM内部LR": "stage_internal_lr",
            "UI/UE/PM验收": "stage_acceptance",
            "冒烟测试": "stage_smoke_test",
            "新功能测试": "stage_new_feature_test",
            "回归测试": "stage_regression_test",
            "灰度阶段": "stage_gray",
            "线上阶段": "stage_online",
        }
        value = stage_value_map.get(issue_stage, "stage_online")  # 默认线上阶段
        return {"label": issue_stage, "value": value}
    
    async def add_comment(self, work_item_id: str, content: str) -> Dict:
        """
        为工作项添加评论
        
        Args:
            work_item_id: 工作项 ID
            content: 评论内容
            
        Returns:
            API 响应
        """
        path = f"/open_api/{self.PROJECT_KEY}/work_item/issue/{work_item_id}/comment/create"
        body = {"content": content}
        return await self._request("POST", path, body)


async def main_async(args):
    """异步主函数"""
    api = FeishuProjectAPI()
    
    # 如果指定了 --load-cache，或者需要用户映射，则加载缓存
    load_cache = getattr(args, 'load_cache', False)
    need_user_mapping = (
        getattr(args, 'reporter', None) or 
        getattr(args, 'operator', None) or
        getattr(args, 'command', None) in ['update', 'create']
    )
    
    if load_cache or (need_user_mapping and not api._cache_loaded):
        # 尝试加载缓存（如果失败不影响后续操作，会回退到静态映射）
        try:
            await api.load_members_cache()
        except Exception as e:
            print(f"⚠️ 警告: 加载用户映射缓存失败，将使用静态映射: {e}")
    
    try:
        command = getattr(args, 'command', None)
        if not command:
            # 兼容旧版本参数格式
            if getattr(args, 'create', False):
                command = 'create'
            elif getattr(args, 'get', False):
                command = 'get'
            elif getattr(args, 'comment', None):
                command = 'comment'
            elif getattr(args, 'work_item_id', None):
                command = 'update'
            else:
                print("❌ 错误: 请指定操作命令 (create/update/get/comment)")
                return 1
        
        if command == 'create':
            # 创建工作项
            name = getattr(args, 'name', None)
            if not name:
                print("❌ 错误: 创建 Bug 时必须提供标题 (--name)")
                return 1
            
            # 处理描述字段中的转义序列
            description = getattr(args, 'description', None)
            if description:
                description = decode_escape_sequences(description)
            
            result = await api.create_work_item(
                work_item_type=getattr(args, 'work_item_type', 'Bugs'),
                name=name,
                priority=getattr(args, 'priority', None),
                severity=getattr(args, 'severity', None),
                bug_classification=getattr(args, 'bug_classification', None),
                issue_stage=getattr(args, 'issue_stage', None),
                description=description,
                business=getattr(args, 'business', None),
                reporter=getattr(args, 'reporter', None),
                operator=getattr(args, 'operator', None)
            )
            
            if result.get("err_code") == 0:
                # 处理响应（参考 jira_feishu_migration.py）
                # 飞书 API 可能直接返回 {"data": 工作项ID} 或 {"data": {"id": 工作项ID}}
                work_item_data = result.get("data")
                if isinstance(work_item_data, dict):
                    work_item_id = work_item_data.get("id") or work_item_data.get("work_item_id")
                elif isinstance(work_item_data, (int, str)):
                    # 直接返回整数 ID 或字符串 ID
                    work_item_id = work_item_data
                else:
                    work_item_id = None
                
                if work_item_id:
                    print(f"✅ Bug 创建成功!")
                    print(f"🔗 https://project.feishu.cn/{FeishuProjectAPI.SIMPLE_NAME}/issue/detail/{work_item_id}")
                    print(f"📋 Work Item ID: {work_item_id}")
                else:
                    # 如果返回格式不同，尝试从返回中提取
                    print(f"✅ Bug 创建成功!")
                    print(f"📋 返回结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
            else:
                print(f"❌ 创建失败: {result}")
                return 1
        
        elif command == 'get':
            # 获取工作项详情
            work_item_id = getattr(args, 'work_item_id', None)
            if not work_item_id:
                print("❌ 错误: 获取工作项详情时必须提供 work_item_id (-w)")
                return 1
            
            result = await api.get_work_item(work_item_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
        elif command == 'comment':
            # 添加评论
            work_item_id = getattr(args, 'work_item_id', None)
            comment = getattr(args, 'comment', None)
            if not work_item_id or not comment:
                print("❌ 错误: 添加评论时必须提供 work_item_id (-w) 和 comment (-c)")
                return 1
            
            # 处理评论字段中的转义序列
            comment = decode_escape_sequences(comment)
            
            result = await api.add_comment(work_item_id, comment)
            if result.get("err_code") == 0:
                print(f"✅ 评论添加成功")
            else:
                print(f"❌ 评论添加失败: {result}")
                return 1
        
        elif command == 'load-cache':
            # 加载用户映射缓存
            cache = await api.load_members_cache()
            if cache:
                print(f"✅ 缓存加载成功，共 {len(cache)} 个用户映射")
            else:
                print("⚠️ 警告: 缓存加载失败或为空")
                return 1
            
        elif command == 'update':
            # 更新工作项
            work_item_id = getattr(args, 'work_item_id', None)
            if not work_item_id:
                print("❌ 错误: 更新工作项时必须提供 work_item_id (-w)")
                return 1
            
            # 处理描述字段中的转义序列
            description = getattr(args, 'description', None)
            if description:
                description = decode_escape_sequences(description)
            
            # 处理评论字段中的转义序列
            comment = getattr(args, 'comment', None)
            if comment:
                comment = decode_escape_sequences(comment)
            
            result = await api.update_work_item(
                work_item_id=work_item_id,
                priority=getattr(args, 'priority', None),
                description=description,
                reporter=getattr(args, 'reporter', None),
                operator=getattr(args, 'operator', None),
                business=getattr(args, 'business', None),
                severity=getattr(args, 'severity', None),
                bug_classification=getattr(args, 'bug_classification', None),
                issue_stage=getattr(args, 'issue_stage', None)
            )
            
            if result.get("err_code") == 0:
                print(f"✅ 更新成功!")
                print(f"🔗 https://project.feishu.cn/{FeishuProjectAPI.SIMPLE_NAME}/issue/detail/{work_item_id}")
            else:
                print(f"❌ 更新失败: {result}")
                return 1
        else:
            print(f"❌ 错误: 未知命令 '{command}'")
            return 1
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="飞书项目 API 工具 - 创建/更新工作项")
    
    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest="command", help="操作命令")
    
    # 创建 Bug 命令
    create_parser = subparsers.add_parser("create", help="创建 Bug/工作项")
    create_parser.add_argument("--name", "-n", required=True, help="Bug 标题")
    create_parser.add_argument("--work_item_type", "-t", default="Bugs", help="工作项类型（默认: Bugs）")
    create_parser.add_argument("--priority", "-p", help="优先级 (P0/P1/P2/P3)")
    create_parser.add_argument("--severity", "-s", help="严重程度 (致命/严重/一般/轻微)")
    create_parser.add_argument("--bug_classification", help="Bug端分类 (iOS/Android/FE/Server)")
    create_parser.add_argument("--issue_stage", help="发现阶段")
    create_parser.add_argument("--description", "-d", help="描述内容（Markdown 格式）")
    create_parser.add_argument("--business", "-b", help="业务线名称")
    create_parser.add_argument("--reporter", "-r", help="报告人用户名")
    create_parser.add_argument("--operator", "-o", help="经办人用户名")
    
    # 更新工作项命令
    update_parser = subparsers.add_parser("update", help="更新工作项")
    update_parser.add_argument("--work_item_id", "-w", required=True, help="工作项 ID")
    update_parser.add_argument("--priority", "-p", help="优先级 (P0/P1/P2/P3)")
    update_parser.add_argument("--description", "-d", help="描述内容（Markdown 格式）")
    update_parser.add_argument("--reporter", "-r", help="报告人用户名")
    update_parser.add_argument("--operator", "-o", help="经办人用户名")
    update_parser.add_argument("--business", "-b", help="业务线名称")
    update_parser.add_argument("--severity", "-s", help="严重程度 (致命/严重/一般/轻微)")
    update_parser.add_argument("--bug_classification", help="Bug端分类 (iOS/Android/FE/Server)")
    update_parser.add_argument("--issue_stage", help="发现阶段")
    
    # 获取工作项详情命令
    get_parser = subparsers.add_parser("get", help="获取工作项详情")
    get_parser.add_argument("--work_item_id", "-w", required=True, help="工作项 ID")
    
    # 添加评论命令
    comment_parser = subparsers.add_parser("comment", help="添加评论")
    comment_parser.add_argument("--work_item_id", "-w", required=True, help="工作项 ID")
    comment_parser.add_argument("--comment", "-c", required=True, help="评论内容")
    
    # 加载缓存命令
    cache_parser = subparsers.add_parser("load-cache", help="加载用户映射缓存")
    
    # 兼容旧版本参数格式（向后兼容）
    parser.add_argument("--work_item_id", "-w", help="工作项 ID（用于更新/查询/评论）")
    parser.add_argument("--description", "-d", help="描述内容（Markdown 格式）")
    parser.add_argument("--reporter", "-r", help="报告人用户名")
    parser.add_argument("--operator", "-o", help="经办人用户名")
    parser.add_argument("--business", "-b", help="业务线名称")
    parser.add_argument("--comment", "-c", help="添加评论")
    parser.add_argument("--get", "-g", action="store_true", help="获取工作项详情")
    parser.add_argument("--create", action="store_true", help="创建 Bug（需要 --name）")
    parser.add_argument("--name", "-n", help="Bug 标题（创建时必填）")
    parser.add_argument("--priority", "-p", help="优先级 (P0/P1/P2/P3)")
    parser.add_argument("--severity", help="严重程度 (致命/严重/一般/轻微)")
    parser.add_argument("--bug_classification", help="Bug端分类 (iOS/Android/FE/Server)")
    parser.add_argument("--issue_stage", help="发现阶段")
    parser.add_argument("--work_item_type", "-t", default="Bugs", help="工作项类型（默认: Bugs）")
    parser.add_argument("--load-cache", action="store_true", help="加载用户映射缓存（首次使用或更新成员时）")
    
    args = parser.parse_args()
    
    # 如果没有指定命令，根据参数判断操作类型
    if not args.command:
        if args.create:
            args.command = "create"
        elif args.get:
            args.command = "get"
        elif args.comment:
            args.command = "comment"
        elif args.work_item_id:
            args.command = "update"
        else:
            parser.print_help()
            return 1
    
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
