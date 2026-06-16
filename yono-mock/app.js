const API = "http://localhost:8000";
const { useState, useEffect, useRef } = React;

const EVENT_LABELS = { salary_increase: "Salary Increase", emi_closure: "EMI Closure", fd_maturity: "FD Maturity", large_expense: "Large Expense", travel_spike: "Travel Spike", education_payment: "Education Payment" };
const EVENT_EMOJI = { salary_increase: "💰", emi_closure: "✅", fd_maturity: "🏦", large_expense: "💳", travel_spike: "✈️", education_payment: "📚" };

function NotificationCard({ event, message, onOpenChat }) {
    const etype = event.event_type;
    const name = (event.customer_name || "Customer").split(" ")[0];
    return React.createElement("div", null,
        React.createElement("div", { className: "notification-card" },
            React.createElement("div", { className: "notif-header" },
                React.createElement("div", { className: "notif-dot" }),
                React.createElement("span", { className: "notif-label" }, "Smart Nudge"),
                React.createElement("span", { className: "notif-time" }, "Just now")
            ),
            React.createElement("span", { className: `event-badge badge-${etype}` }, `${EVENT_EMOJI[etype] || "📌"} ${EVENT_LABELS[etype]}`),
            React.createElement("p", { className: "greeting" }, `Hi ${name}! 👋`),
            React.createElement("p", { className: "message-text" }, message ? message.message : "We have a personalised offer for you!"),
            message && React.createElement("div", { className: "product-tag" }, "🎯 ", message.product)
        ),
        React.createElement("button", {
            className: "cta-button",
            onClick: onOpenChat
        }, "📲 View Offer on YONO")
    );
}

function ChatAdvisor({ event, message, onClose, onStatusChange }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [typing, setTyping] = useState(false);
    const messagesEndRef = useRef(null);
    const name = (event.customer_name || "Customer").split(" ")[0];

    useEffect(() => {
        if (message) {
            const initial = {
                role: "assistant",
                text: `Hi ${name}! I saw your recent ${event.event_type.replace('_', ' ')}. I highly recommend ${message.product} for you. Would you like to check details or apply instantly?`
            };
            setMessages(message.chat_history && message.chat_history.length > 0 ? message.chat_history : [initial]);
        }
    }, [message]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, typing]);

    const handleSend = (text) => {
        if (!text.trim()) return;
        const userMsg = { role: "user", text };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setTyping(true);

        fetch(`${API}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ customer_id: event.customer_id, message_id: message.id, user_message: text })
        })
            .then(r => r.json())
            .then(data => {
                setTyping(false);
                setMessages(data.chat_history);
                if (data.status === "converted") onStatusChange("converted");
            })
            .catch(() => setTyping(false));
    };

    return React.createElement("div", { className: "chat-container" },
        React.createElement("div", { className: "chat-header" },
            React.createElement("button", { className: "chat-back", onClick: onClose }, "←"),
            React.createElement("div", { className: "chat-avatar" }, "🤖"),
            React.createElement("div", { className: "chat-title" },
                React.createElement("h4", null, "SBI AI Advisor"),
                React.createElement("span", null, "Online")
            )
        ),
        React.createElement("div", { className: "chat-messages" },
            messages.map((m, i) => React.createElement("div", { key: i, className: `msg-bubble ${m.role === 'user' ? 'user' : 'bot'}` }, m.text)),
            typing && React.createElement("div", { className: "typing-indicator" }, React.createElement("span"), React.createElement("span"), React.createElement("span")),
            React.createElement("div", { ref: messagesEndRef })
        ),
        React.createElement("div", { className: "chat-quick-actions" },
            React.createElement("button", { className: "quick-reply-btn", onClick: () => handleSend("What are the key benefits?") }, "💡 Benefits?"),
            React.createElement("button", { className: "quick-reply-btn", onClick: () => handleSend("What are the interest rates?") }, "📊 Rates?"),
            React.createElement("button", { className: "quick-reply-btn", onClick: () => handleSend("Apply Instantly") }, "✅ Apply Now")
        ),
        React.createElement("form", {
            className: "chat-input-bar",
            onSubmit: (e) => { e.preventDefault(); handleSend(input); }
        },
            React.createElement("input", { value: input, onChange: e => setInput(e.target.value), placeholder: "Ask AI Advisor..." }),
            React.createElement("button", { type: "submit", className: "chat-send-btn" }, "→")
        )
    );
}

function App() {
    const [events, setEvents] = useState([]);
    const [messages, setMessages] = useState({});
    const [selected, setSelected] = useState(0);
    const [view, setView] = useState("nudges"); // nudges, chat

    const loadData = () => {
        fetch(`${API}/events`)
            .then(r => r.json())
            .then(data => {
                const evts = (data.events || []).slice(0, 15);
                setEvents(evts);
                const msgsMap = {};
                evts.forEach(e => {
                    if (e.message_id) {
                        msgsMap[e.id] = {
                            id: e.message_id,
                            customer_id: e.customer_id,
                            event_id: e.id,
                            product: e.product,
                            message: e.message,
                            status: e.status || "detected",
                            chat_history: e.chat_history || []
                        };
                    }
                });
                setMessages(msgsMap);
            });
    };

    const strId = id => id ? String(id) : "";

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 5000); // Polling every 5 seconds for live simulation
        return () => clearInterval(interval);
    }, []);

    const currentEvent = events[selected];
    const currentMsg = currentEvent ? messages[currentEvent.id] : null;

    const handleOpenChat = () => {
        if (!currentMsg) return;
        fetch(`${API}/messages/${currentMsg.id}/status?status=clicked`, { method: "POST" })
            .then(() => {
                loadData();
                setView("chat");
            });
    };

    const renderMain = () => {
        if (events.length === 0) {
            return React.createElement("div", { className: "empty-state" },
                React.createElement("div", { className: "icon" }, "🔔"),
                React.createElement("p", null, "No events detected yet."),
                React.createElement("p", null, "Run the pipeline or inject transactions in the dashboard.")
            );
        }
        if (view === "chat" && currentEvent && currentMsg) {
            return React.createElement(ChatAdvisor, {
                event: currentEvent, message: currentMsg,
                onClose: () => setView("nudges"),
                onStatusChange: () => loadData()
            });
        }
        return currentEvent && React.createElement(NotificationCard, {
            event: currentEvent, message: currentMsg, onOpenChat: handleOpenChat
        });
    };

    return React.createElement("div", { className: "phone-frame" },
        React.createElement("div", { className: "status-bar" },
            React.createElement("span", { className: "time" }, new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: false })),
            React.createElement("div", { className: "status-icons" }, "📶 🔋")
        ),
        React.createElement("div", { className: "yono-header" },
            React.createElement("div", { className: "sbi-logo" }, "SBI"),
            React.createElement("div", { className: "header-text" },
                React.createElement("h2", null, "YONO SBI"),
                React.createElement("span", null, "ENGAGE AI • CHAT ADVISOR")
            )
        ),
        view === "nudges" && events.length > 0 && React.createElement("div", { className: "selector-bar" },
            events.map((e, i) =>
                React.createElement("button", {
                    key: e.id,
                    className: `selector-chip ${i === selected ? "active" : ""}`,
                    onClick: () => setSelected(i),
                }, (e.customer_name || "Customer").split(" ")[0])
            )
        ),
        renderMain(),
        React.createElement("div", { className: "bottom-nav" },
            ["🏠", "💳", "💬", "👤"].map((icon, i) =>
                React.createElement("div", { key: i, className: `nav-item ${i === 2 ? "active" : ""}` },
                    React.createElement("span", { className: "icon" }, icon),
                    React.createElement("span", null, ["Home", "Accounts", "Advisor", "Profile"][i])
                )
            )
        )
    );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(React.createElement(App));
