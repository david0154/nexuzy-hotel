# NEX Hotel AI - Lightweight AI Engine
# Using Mistral 7B / LLaMA 3 8B with QLoRA optimization

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3

class NEXHotelAI:
    """
    Lightweight AI engine for hotel management.
    Optimized for low RAM usage (4-8 GB).
    
    Will be integrated with:
    - Mistral 7B (quantized)
    - LLaMA 3 8B (4-bit)
    - ONNX Runtime for optimization
    """
    
    def __init__(self, db_path: str = "../nexuzy_hotel.db"):
        self.db_path = db_path
        self.intents = self._load_intents()
    
    def _load_intents(self) -> Dict:
        """Load AI intent patterns"""
        return {
            "booking": [
                r"book.*room",
                r"reserve.*room",
                r"make.*reservation",
                r"i need.*room",
                r"i want.*book"
            ],
            "search_rooms": [
                r"find.*room",
                r"available.*room",
                r"show.*room",
                r"any.*room.*available",
                r"check.*availability"
            ],
            "analytics": [
                r"revenue",
                r"income",
                r"earnings",
                r"profit",
                r"how much.*made",
                r"show.*trend"
            ],
            "trip_planning": [
                r"plan.*trip",
                r"travel.*plan",
                r"itinerary",
                r"tour.*package",
                r"vacation.*plan"
            ]
        }
    
    def process_command(self, command: str, user_context: Optional[Dict] = None) -> Dict:
        """
        Process natural language command.
        
        Examples:
        - "Book 2 deluxe rooms from 12-15 July"
        - "Find available rooms for tomorrow"
        - "Show revenue for last week"
        - "Plan Goa trip for 2 people under ₹18,000"
        """
        intent = self._detect_intent(command)
        
        if intent == "booking":
            return self._handle_booking(command, user_context)
        elif intent == "search_rooms":
            return self._handle_search(command)
        elif intent == "analytics":
            return self._handle_analytics(command)
        elif intent == "trip_planning":
            return self._handle_trip_planning(command, user_context)
        else:
            return self._handle_general(command)
    
    def _detect_intent(self, command: str) -> str:
        """Detect user intent from command"""
        cmd_lower = command.lower()
        
        for intent, patterns in self.intents.items():
            for pattern in patterns:
                if re.search(pattern, cmd_lower):
                    return intent
        
        return "general"
    
    def _handle_booking(self, command: str, context: Optional[Dict]) -> Dict:
        """Handle booking requests"""
        # Extract entities from command
        entities = self._extract_booking_entities(command)
        
        # Search available rooms
        rooms = self._search_available_rooms(
            check_in=entities.get('check_in'),
            check_out=entities.get('check_out'),
            room_type=entities.get('room_type'),
            num_rooms=entities.get('num_rooms', 1)
        )
        
        if not rooms:
            return {
                "success": False,
                "message": "No rooms available for your dates.",
                "action": "suggest_alternatives",
                "suggestions": self._suggest_alternative_dates(entities)
            }
        
        # Calculate pricing
        pricing = self._calculate_pricing(rooms, entities)
        
        return {
            "success": True,
            "action": "booking",
            "message": f"Found {len(rooms)} available rooms",
            "rooms": rooms,
            "pricing": pricing,
            "entities": entities
        }
    
    def _handle_search(self, command: str) -> Dict:
        """Handle room search queries"""
        entities = self._extract_search_entities(command)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM rooms WHERE status='Available'"
            params = []
            
            if entities.get('room_type'):
                query += " AND room_type=?"
                params.append(entities['room_type'])
            
            cursor.execute(query, params)
            rooms = [dict(zip([col[0] for col in cursor.description], row)) 
                    for row in cursor.fetchall()]
        
        return {
            "success": True,
            "action": "room_list",
            "message": f"Found {len(rooms)} available rooms",
            "rooms": rooms
        }
    
    def _handle_analytics(self, command: str) -> Dict:
        """Handle analytics and reporting queries"""
        period = self._extract_time_period(command)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Calculate revenue
            cursor.execute("""
                SELECT 
                    DATE(check_out) as date,
                    COUNT(*) as bookings,
                    SUM(total_amount) as revenue
                FROM bookings
                WHERE status='Checked-Out'
                AND check_out >= date('now', ?)
                GROUP BY DATE(check_out)
                ORDER BY date DESC
            """, (period,))
            
            data = [dict(zip([col[0] for col in cursor.description], row)) 
                   for row in cursor.fetchall()]
            
            total_revenue = sum(d['revenue'] or 0 for d in data)
            total_bookings = sum(d['bookings'] for d in data)
        
        return {
            "success": True,
            "action": "analytics",
            "message": f"Analytics for {period}",
            "data": data,
            "summary": {
                "total_revenue": total_revenue,
                "total_bookings": total_bookings,
                "average_per_booking": total_revenue / max(total_bookings, 1)
            }
        }
    
    def _handle_trip_planning(self, command: str, context: Optional[Dict]) -> Dict:
        """
        Handle travel planning requests.
        
        Example: "Plan Goa trip for 2 people under ₹18,000"
        """
        entities = self._extract_trip_entities(command)
        
        # Search hotels in destination
        hotels = self._search_hotels_in_location(
            location=entities.get('destination'),
            budget=entities.get('budget'),
            people=entities.get('people', 2)
        )
        
        # Create trip plan
        trip_plan = self._create_trip_plan(
            destination=entities.get('destination'),
            hotels=hotels,
            budget=entities.get('budget'),
            people=entities.get('people')
        )
        
        return {
            "success": True,
            "action": "trip_plan",
            "message": f"Created trip plan for {entities.get('destination')}",
            "plan": trip_plan,
            "hotels": hotels,
            "total_cost": trip_plan['total_cost']
        }
    
    def _handle_general(self, command: str) -> Dict:
        """Handle general queries"""
        return {
            "success": True,
            "action": "general",
            "message": "I can help you with:",
            "suggestions": [
                "Book rooms: 'Book 2 deluxe rooms from 12-15 July'",
                "Search: 'Find available rooms for tomorrow'",
                "Analytics: 'Show revenue for last month'",
                "Trip planning: 'Plan Goa trip for 2 people under ₹18,000'"
            ]
        }
    
    def _extract_booking_entities(self, command: str) -> Dict:
        """Extract booking entities from command"""
        entities = {}
        
        # Extract dates
        date_patterns = [
            r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})',  # DD-MM-YYYY
            r'from\s+(\w+\s+\d{1,2})',  # from July 12
            r'tomorrow',
            r'next\s+(\w+)'  # next monday
        ]
        
        # Extract room type
        room_types = ['deluxe', 'ac', 'non-ac', 'suite', 'standard']
        for rt in room_types:
            if rt in command.lower():
                entities['room_type'] = rt.title()
                break
        
        # Extract number of rooms
        num_match = re.search(r'(\d+)\s+room', command.lower())
        if num_match:
            entities['num_rooms'] = int(num_match.group(1))
        
        # Extract number of people
        people_match = re.search(r'for\s+(\d+)\s+people', command.lower())
        if people_match:
            entities['people'] = int(people_match.group(1))
        
        return entities
    
    def _extract_search_entities(self, command: str) -> Dict:
        """Extract search criteria"""
        entities = {}
        
        room_types = ['deluxe', 'ac', 'non-ac', 'suite', 'standard']
        for rt in room_types:
            if rt in command.lower():
                entities['room_type'] = rt.title()
                break
        
        return entities
    
    def _extract_time_period(self, command: str) -> str:
        """Extract time period for analytics"""
        if 'week' in command.lower():
            return '-7 days'
        elif 'month' in command.lower():
            return '-30 days'
        elif 'year' in command.lower():
            return '-365 days'
        else:
            return '-30 days'
    
    def _extract_trip_entities(self, command: str) -> Dict:
        """Extract trip planning entities"""
        entities = {}
        
        # Extract destination
        destinations = ['goa', 'mumbai', 'delhi', 'jaipur', 'bangalore']
        for dest in destinations:
            if dest in command.lower():
                entities['destination'] = dest.title()
                break
        
        # Extract budget
        budget_match = re.search(r'₹?([\d,]+)', command)
        if budget_match:
            entities['budget'] = float(budget_match.group(1).replace(',', ''))
        
        # Extract number of people
        people_match = re.search(r'for\s+(\d+)\s+people', command.lower())
        if people_match:
            entities['people'] = int(people_match.group(1))
        
        return entities
    
    def _search_available_rooms(self, check_in, check_out, room_type=None, num_rooms=1):
        """Search for available rooms"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM rooms WHERE status='Available'"
            params = []
            
            if room_type:
                query += " AND room_type=?"
                params.append(room_type)
            
            query += " LIMIT ?"
            params.append(num_rooms)
            
            cursor.execute(query, params)
            return [dict(zip([col[0] for col in cursor.description], row)) 
                   for row in cursor.fetchall()]
    
    def _calculate_pricing(self, rooms: List[Dict], entities: Dict) -> Dict:
        """Calculate total pricing for booking"""
        total = sum(room['rate'] for room in rooms)
        nights = entities.get('nights', 1)
        
        room_cost = total * nights
        tax = room_cost * 0.18  # 18% GST
        total_cost = room_cost + tax
        
        return {
            "room_cost": room_cost,
            "tax": tax,
            "total": total_cost,
            "per_night": total,
            "nights": nights
        }
    
    def _suggest_alternative_dates(self, entities: Dict) -> List[str]:
        """Suggest alternative dates when rooms not available"""
        return [
            "Try dates 1 day later",
            "Try dates 1 week later",
            "Check different room type"
        ]
    
    def _search_hotels_in_location(self, location, budget, people):
        """Search hotels in destination (placeholder)"""
        # This will integrate with external hotel APIs
        return []
    
    def _create_trip_plan(self, destination, hotels, budget, people):
        """Create comprehensive trip plan"""
        hotel_cost = budget * 0.6  # 60% for hotel
        transport_cost = budget * 0.2  # 20% for transport
        food_cost = budget * 0.15  # 15% for food
        activities_cost = budget * 0.05  # 5% for activities
        
        return {
            "destination": destination,
            "people": people,
            "breakdown": {
                "hotel": hotel_cost,
                "transport": transport_cost,
                "food": food_cost,
                "activities": activities_cost
            },
            "total_cost": budget,
            "suggestions": [
                f"Book {destination} hotel within ₹{hotel_cost}",
                f"Budget ₹{food_cost} for food per person",
                f"Keep ₹{activities_cost} for activities"
            ]
        }

# Example usage
if __name__ == "__main__":
    ai = NEXHotelAI()
    
    # Test commands
    commands = [
        "Book 2 deluxe rooms from 12-15 July",
        "Find available AC rooms",
        "Show revenue for last month",
        "Plan Goa trip for 2 people under ₹18,000"
    ]
    
    for cmd in commands:
        print(f"\nCommand: {cmd}")
        result = ai.process_command(cmd)
        print(json.dumps(result, indent=2))