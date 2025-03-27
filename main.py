from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import os
import logging
import requests
import shutil
from datetime import datetime
from pathlib import Path
import json

class ImageManager:
    FOLDER_NAME = "WZL_NachonekoPlus"

    def __init__(self, config: dict):
        self.config = config
        self._init_logger()
        self.storage_path = self._validate_storage_path()
        self._verify_permissions()

    def _init_logger(self):
        self.logger = logging.getLogger('WZLNekoPlugin')
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(
            Path(__file__).parent / "WZL_NachonekoPlus.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.logger.addHandler(file_handler)

    def _validate_storage_path(self) -> Path:
        base_path = Path(self.config['storage_path']).resolve()
        return base_path / self.FOLDER_NAME

    def _verify_permissions(self):
        test_file = self.storage_path / ".perm_test"
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            self.logger.error(f"权限验证失败: {str(e)}")
            raise

    def fetch_image(self) -> str:
        try:
            resp = requests.get('https://api.suyanw.cn/api/mao', timeout=15)
            resp.raise_for_status()
            
            if 'image/' not in resp.headers.get('Content-Type', ''):
                raise ValueError("非图片响应")
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            ext = resp.headers['Content-Type'].split('/')[-1]
            save_path = self.storage_path / f"neko_{timestamp}.{ext}"
            
            with open(save_path, 'wb') as f:
                f.write(resp.content)
                
            self.logger.info(f"图片已保存: {save_path}")
            return str(save_path)
            
        except Exception as e:
            self.logger.error(f"获取失败: {str(e)}")
            return None

@register("astrbot_plugin_WZL_NachonekoPlus", "WZL", "甘城猫猫图片插件", "1.0.6", "https://github.com/WZL0813/astrbot_plugin_WZL_NachonekoPlus")
class NachonekoPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = self._load_config()
        self.manager = ImageManager(self.config)

    def _load_config(self) -> dict:
        config_path = Path(__file__).parent / "_conf_schema.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            
        user_config = getattr(self.context, 'plugin_config', {})
        config = {}
        
        for key in schema:
            expected_type = schema[key]['type']
            default_value = schema[key]['default']
            
            if expected_type == 'bool':
                config[key] = bool(user_config.get(key, default_value))
            else:
                config[key] = type(default_value)(user_config.get(key, default_value))
                
        config['storage_path'] = str(Path(config['storage_path']).resolve())
        return config

    @filter.command("neko")
    async def send_image(self, event: AstrMessageEvent):
        """处理/neko指令"""
        try:
            # 第一阶段：立即回复文本
            yield event.plain_result("喵喵喵~")
            
            # 第二阶段：获取并发送图片
            img_path = self.manager.fetch_image()
            if not img_path:
                yield event.plain_result("暂时无法获取图片，请稍后再试")
                return
                
            yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
            
            # 第三阶段：非永久模式清理
            if not self.config['keep_images']:
                os.remove(img_path)
                self.manager.logger.info(f"临时图片已删除: {img_path}")
                
        except requests.Timeout:
            yield event.plain_result("请求超时，猫猫正在偷懒~")
        except Exception as e:
            self.manager.logger.error(f"处理失败: {str(e)}")
            yield event.plain_result("服务异常，快去找管理员修喵！")

    async def terminate(self):
        if not self.config['keep_images']:
            shutil.rmtree(self.manager.storage_path, ignore_errors=True)
