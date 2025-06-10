"""
WebSocket consumers for real-time dashboard updates.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import UserDashboard, DashboardWidget


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time dashboard updates.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        self.dashboard_id = self.scope['url_route']['kwargs'].get('dashboard_id')
        
        # Only authenticated users can connect
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Join dashboard group
        if self.dashboard_id:
            self.dashboard_group_name = f'dashboard_{self.dashboard_id}'
        else:
            # Default dashboard group for the user
            self.dashboard_group_name = f'user_dashboard_{self.user.id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.dashboard_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial connection message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to dashboard updates'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        if hasattr(self, 'dashboard_group_name'):
            await self.channel_layer.group_discard(
                self.dashboard_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'subscribe_widget':
                widget_id = text_data_json.get('widget_id')
                if widget_id:
                    await self.subscribe_to_widget(widget_id)
            
            elif message_type == 'request_widget_update':
                widget_id = text_data_json.get('widget_id')
                if widget_id:
                    await self.send_widget_update(widget_id)
                    
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    async def subscribe_to_widget(self, widget_id):
        """Subscribe to updates for a specific widget."""
        # Verify user has access to this widget
        has_access = await self.check_widget_access(widget_id)
        
        if has_access:
            widget_group_name = f'widget_{widget_id}'
            await self.channel_layer.group_add(
                widget_group_name,
                self.channel_name
            )
            
            await self.send(text_data=json.dumps({
                'type': 'widget_subscribed',
                'widget_id': widget_id
            }))
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Access denied for widget'
            }))
    
    async def send_widget_update(self, widget_id):
        """Send widget data update."""
        widget_data = await self.get_widget_data(widget_id)
        
        if widget_data:
            await self.send(text_data=json.dumps({
                'type': 'widget_update',
                'widget_id': widget_id,
                'data': widget_data,
                'timestamp': json.dumps(timezone.now(), default=str)
            }))
    
    @database_sync_to_async
    def check_widget_access(self, widget_id):
        """Check if user has access to a widget."""
        try:
            widget = DashboardWidget.objects.get(id=widget_id)
            
            # Check access permissions
            if widget.is_public:
                return True
            if widget.created_by == self.user:
                return True
            if self.user in widget.shared_with.all():
                return True
                
            return False
        except DashboardWidget.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_widget_data(self, widget_id):
        """Get widget data."""
        try:
            widget = DashboardWidget.objects.get(id=widget_id)
            return widget.get_data(user=self.user)
        except DashboardWidget.DoesNotExist:
            return None
    
    # Handler for different message types
    async def widget_update(self, event):
        """Send widget update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'widget_update',
            'widget_id': event['widget_id'],
            'data': event['data'],
            'timestamp': event['timestamp']
        }))
    
    async def dashboard_notification(self, event):
        """Send dashboard notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'title': event['title'],
            'message': event['message'],
            'level': event.get('level', 'info'),
            'timestamp': event['timestamp']
        }))
    
    async def system_message(self, event):
        """Send system message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'system_message',
            'message': event['message'],
            'timestamp': event['timestamp']
        }))
