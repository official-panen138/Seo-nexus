import { useState } from 'react';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { 
    AlertTriangle, 
    CheckCircle, 
    Clock, 
    MessageSquare, 
    User,
    ChevronDown,
    ChevronUp,
    Flag,
    ArrowRight
} from 'lucide-react';

/**
 * ComplaintTimeline Component
 * 
 * Renders a visual timeline showing the chronological history of complaints
 * and their associated responses for an optimization.
 * 
 * Events displayed:
 * - Complaint Created (red marker)
 * - Team Response (blue marker)  
 * - Complaint Resolved (green marker)
 */

const EVENT_TYPES = {
    COMPLAINT_CREATED: 'complaint_created',
    TEAM_RESPONSE: 'team_response',
    COMPLAINT_RESOLVED: 'complaint_resolved'
};

const EVENT_CONFIG = {
    [EVENT_TYPES.COMPLAINT_CREATED]: {
        icon: AlertTriangle,
        color: 'text-red-400',
        bgColor: 'bg-red-500/20',
        borderColor: 'border-red-500/50',
        lineColor: 'bg-red-500/30',
        label: 'Complaint Filed'
    },
    [EVENT_TYPES.TEAM_RESPONSE]: {
        icon: MessageSquare,
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/20',
        borderColor: 'border-blue-500/50',
        lineColor: 'bg-blue-500/30',
        label: 'Team Response'
    },
    [EVENT_TYPES.COMPLAINT_RESOLVED]: {
        icon: CheckCircle,
        color: 'text-emerald-400',
        bgColor: 'bg-emerald-500/20',
        borderColor: 'border-emerald-500/50',
        lineColor: 'bg-emerald-500/30',
        label: 'Resolved'
    }
};

const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
    });
};

const formatRelativeTime = (dateStr) => {
    if (!dateStr) return '';
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(dateStr);
};

const TimelineEvent = ({ event, isLast, isExpanded, onToggle }) => {
    const config = EVENT_CONFIG[event.type];
    const Icon = config.icon;
    
    return (
        <div className="relative flex gap-4" data-testid={`timeline-event-${event.id}`}>
            {/* Timeline Line */}
            {!isLast && (
                <div 
                    className={`absolute left-[15px] top-[36px] w-0.5 h-[calc(100%-20px)] ${config.lineColor}`}
                />
            )}
            
            {/* Event Marker */}
            <div 
                className={`flex-shrink-0 w-8 h-8 rounded-full ${config.bgColor} border ${config.borderColor} flex items-center justify-center z-10`}
            >
                <Icon className={`h-4 w-4 ${config.color}`} />
            </div>
            
            {/* Event Content */}
            <div className="flex-1 pb-6">
                <div 
                    className="flex items-center justify-between cursor-pointer hover:bg-zinc-800/30 p-2 rounded-lg -ml-2"
                    onClick={onToggle}
                >
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className={`font-medium text-sm ${config.color}`}>
                            {config.label}
                        </span>
                        {event.complaintNum && (
                            <Badge variant="outline" className="text-xs">
                                #{event.complaintNum}
                            </Badge>
                        )}
                        {event.priority && (
                            <Badge 
                                className={`text-xs ${
                                    event.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                                    event.priority === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                                    'bg-zinc-500/20 text-zinc-400'
                                }`}
                            >
                                {event.priority.charAt(0).toUpperCase() + event.priority.slice(1)} Priority
                            </Badge>
                        )}
                        {event.resolutionTime && (
                            <Badge className="bg-emerald-500/20 text-emerald-400 text-xs gap-1">
                                <Clock className="h-3 w-3" />
                                {event.resolutionTime.toFixed(1)}h
                            </Badge>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500">
                            {formatRelativeTime(event.timestamp)}
                        </span>
                        {isExpanded ? (
                            <ChevronUp className="h-4 w-4 text-zinc-500" />
                        ) : (
                            <ChevronDown className="h-4 w-4 text-zinc-500" />
                        )}
                    </div>
                </div>
                
                {/* Expanded Details */}
                {isExpanded && (
                    <div className="mt-2 p-3 rounded-lg bg-zinc-900/50 border border-zinc-800 ml-0">
                        <div className="space-y-2">
                            {/* Actor Info */}
                            <div className="flex items-center gap-2 text-xs text-zinc-400">
                                <User className="h-3 w-3" />
                                <span>{event.actor}</span>
                                <span className="text-zinc-600">•</span>
                                <span>{formatDate(event.timestamp)}</span>
                            </div>
                            
                            {/* Event Content */}
                            {event.content && (
                                <p className="text-sm text-zinc-300 whitespace-pre-wrap mt-2">
                                    {event.content}
                                </p>
                            )}
                            
                            {/* Responsible Users (for complaints) */}
                            {event.responsibleUsers?.length > 0 && (
                                <div className="mt-2">
                                    <p className="text-xs text-zinc-500 mb-1">Assigned to:</p>
                                    <div className="flex flex-wrap gap-1">
                                        {event.responsibleUsers.map((user, idx) => (
                                            <Badge key={idx} variant="secondary" className="text-xs">
                                                @{user.name || user.email}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {/* Report URLs */}
                            {event.reportUrls?.length > 0 && (
                                <div className="mt-2">
                                    <p className="text-xs text-zinc-500 mb-1">Evidence:</p>
                                    <div className="flex flex-wrap gap-1">
                                        {event.reportUrls.map((url, idx) => (
                                            <a 
                                                key={idx}
                                                href={url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                            >
                                                <ArrowRight className="h-3 w-3" />
                                                Link {idx + 1}
                                            </a>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default function ComplaintTimeline({ complaints = [], responses = [] }) {
    const [expandedEvents, setExpandedEvents] = useState({});
    
    // Build timeline events from complaints and responses
    const buildTimelineEvents = () => {
        const events = [];
        
        // Add complaint events
        complaints.forEach((complaint, idx) => {
            const complaintNum = complaints.length - idx;
            
            // Complaint Created event
            events.push({
                id: `complaint-${complaint.id}`,
                type: EVENT_TYPES.COMPLAINT_CREATED,
                timestamp: complaint.created_at,
                actor: complaint.created_by?.display_name || 'Unknown',
                content: complaint.reason,
                complaintNum,
                priority: complaint.priority,
                responsibleUsers: complaint.responsible_users || [],
                reportUrls: complaint.report_urls || [],
                complaintId: complaint.id
            });
            
            // Complaint Resolved event (if resolved)
            if (complaint.resolved_at) {
                events.push({
                    id: `resolved-${complaint.id}`,
                    type: EVENT_TYPES.COMPLAINT_RESOLVED,
                    timestamp: complaint.resolved_at,
                    actor: complaint.resolved_by?.display_name || 'Unknown',
                    content: complaint.resolution_note,
                    complaintNum,
                    resolutionTime: complaint.time_to_resolution_hours,
                    complaintId: complaint.id
                });
            }
        });
        
        // Add team response events
        responses.forEach((response) => {
            events.push({
                id: `response-${response.id}`,
                type: EVENT_TYPES.TEAM_RESPONSE,
                timestamp: response.created_at,
                actor: response.created_by?.display_name || 'Unknown',
                content: response.note,
                reportUrls: response.report_urls || [],
                complaintId: response.complaint_id
            });
        });
        
        // Sort by timestamp (oldest first for chronological order)
        events.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        
        return events;
    };
    
    const timelineEvents = buildTimelineEvents();
    
    const toggleEvent = (eventId) => {
        setExpandedEvents(prev => ({
            ...prev,
            [eventId]: !prev[eventId]
        }));
    };
    
    // Calculate summary stats
    const totalComplaints = complaints.length;
    const resolvedComplaints = complaints.filter(c => c.resolved_at).length;
    const totalResponses = responses.length;
    const avgResolutionTime = complaints
        .filter(c => c.time_to_resolution_hours)
        .reduce((sum, c, _, arr) => sum + c.time_to_resolution_hours / arr.length, 0) || null;
    
    if (timelineEvents.length === 0) {
        return null;
    }
    
    return (
        <Card className="bg-zinc-900/50 border-border" data-testid="complaint-timeline">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                        <Flag className="h-4 w-4" />
                        Complaint Timeline
                    </CardTitle>
                    <div className="flex gap-2">
                        <Badge variant="outline" className="text-xs">
                            {resolvedComplaints}/{totalComplaints} Resolved
                        </Badge>
                        {avgResolutionTime && (
                            <Badge className="bg-zinc-800 text-zinc-300 text-xs gap-1">
                                <Clock className="h-3 w-3" />
                                Avg: {avgResolutionTime.toFixed(1)}h
                            </Badge>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {/* Timeline Summary Stats */}
                <div className="flex gap-4 mb-4 p-2 rounded-lg bg-zinc-800/30">
                    <div className="flex items-center gap-2 text-xs">
                        <div className="w-2 h-2 rounded-full bg-red-500" />
                        <span className="text-zinc-400">{totalComplaints} Complaints</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        <span className="text-zinc-400">{totalResponses} Responses</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <span className="text-zinc-400">{resolvedComplaints} Resolved</span>
                    </div>
                </div>
                
                {/* Timeline Events */}
                <div className="relative">
                    {timelineEvents.map((event, index) => (
                        <TimelineEvent
                            key={event.id}
                            event={event}
                            isLast={index === timelineEvents.length - 1}
                            isExpanded={expandedEvents[event.id]}
                            onToggle={() => toggleEvent(event.id)}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}
