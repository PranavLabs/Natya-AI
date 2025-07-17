import React, { useState, useEffect, useRef } from 'react';

export default function App() {
  // messages state will now mirror the backend's history structure:
  // { role: 'user' | 'assistant', content: string, recommendations?: Array<{ title: string, description: string, type: string }> }
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [mediaType, setMediaType] = useState(null); // 'movie' or 'tv'
  const [isLoading, setIsLoading] = useState(false);
  const [currentView, setCurrentView] = useState('chat'); // 'chat' or 'about'
  const messagesEndRef = useRef(null);

  // IMPORTANT: For Vercel monorepo setup, API_BASE_URL points to the relative path of your serverless function.
  // This should be '/api' if your FastAPI app is served under /api/
  const API_BASE_URL = "/api"; 

  // Scroll to the latest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initial greeting message
  useEffect(() => {
    if (currentView === 'chat' && messages.length === 0) {
      setMessages([
        { role: 'assistant', content: "Hello! I'm your Movie/TV Show Recommendation Assistant. What are you in the mood for today?" },
        { role: 'assistant', content: "Do you want to search for a **movie** or a **tv show**?" }
      ]);
    }
  }, [currentView, messages.length]);

  const handleSendMessage = async () => {
    if (inputValue.trim() === '') return;

    const userMessageText = inputValue.trim();
    const newUserMessage = { role: 'user', content: userMessageText };

    // Optimistically add user message to display
    setMessages((prevMessages) => [...prevMessages, newUserMessage]);
    setInputValue('');
    setIsLoading(true);

    let currentMediaType = mediaType;

    // First, determine media type if not already set
    if (!currentMediaType) {
      if (userMessageText.toLowerCase().includes('movie')) {
        currentMediaType = 'movie';
        setMediaType('movie');
        setMessages((prevMessages) => [...prevMessages, { role: 'assistant', content: "Great! Tell me about the **movie** you're looking for (genre, mood, style, year, language/industry, etc.)." }]);
        setIsLoading(false);
        return; // Stop here, wait for the next user input for actual recommendation
      } else if (userMessageText.toLowerCase().includes('tv') || userMessageText.toLowerCase().includes('show') || userMessageText.toLowerCase().includes('series')) {
        currentMediaType = 'tv';
        setMediaType('tv');
        setMessages((prevMessages) => [...prevMessages, { role: 'assistant', content: "Awesome! Tell me about the **TV show** you're looking for (genre, mood, style, year, language/industry, etc.)." }]);
        setIsLoading(false);
        return; // Stop here, wait for the next user input for actual recommendation
      } else {
        setMessages((prevMessages) => [...prevMessages, { role: 'assistant', content: "Please specify if you're looking for a **movie** or a **tv show**." }]);
        setIsLoading(false);
        return;
      }
    }

    // If mediaType is set, proceed with recommendation request
    try {
      const apiUrl = `${API_BASE_URL}/chat`; // <<< Changed to /api/chat

      // Prepare the history to send to the backend
      // It should include all previous messages + the current user message
      // Only send 'role' and 'content' for history to backend
      const historyToSend = messages.map(msg => ({ role: msg.role, content: msg.content }));
      historyToSend.push({ role: newUserMessage.role, content: newUserMessage.content });

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_message: userMessageText,
          media_type: currentMediaType, // Use the determined media type
          history: historyToSend 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // *** MODIFIED LOGIC HERE ***
      // The backend now returns the full updated history, and a separate 'recommendations' array.
      // We need to ensure the LAST message in the history state also contains these recommendations.
      const updatedHistoryFromBackend = data.history;
      const latestBotMessage = updatedHistoryFromBackend[updatedHistoryFromBackend.length - 1];
      
      // Create a new message object for the frontend that includes recommendations
      const formattedLatestBotMessage = {
        ...latestBotMessage, // Copy role and content
        recommendations: data.recommendations // Add the structured recommendations
      };

      // Replace the last message in the history with our formatted one
      const finalMessagesForFrontend = [
        ...updatedHistoryFromBackend.slice(0, updatedHistoryFromBackend.length - 1),
        formattedLatestBotMessage
      ];

      setMessages(finalMessagesForFrontend);

    } catch (error) {
      console.error('API call failed:', error);
      setMessages((prevMessages) => [...prevMessages, { role: 'assistant', content: `Oops! Something went wrong: ${error.message}. Please try again.` }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Helper function to render recommendations
  const renderRecommendations = (recs) => {
    if (!recs || recs.length === 0) return null;

    return (
      <div style={recommendationsContainerStyle}>
        {/* Removed the "Recommendations:" title here, as the AI's ai_message will contain introductory text */}
        <ul style={recommendationsListStyle}>
          {recs.map((rec, idx) => (
            <li key={idx} style={recommendationItemStyle}>
              <strong style={recommendationTitleStyle}>{rec.title}</strong>
              <p style={recommendationDescriptionStyle}>{rec.description}</p>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div style={chatContainerStyle}>
      {/* Internal CSS for basic layout and animation */}
      <style>
        {`
        /* Basic Flexbox Utilities */
        .flex { display: flex; }
        .flex-col { flex-direction: column; }
        .flex-1 { flex: 1; }
        .justify-end { justify-content: flex-end; }
        .justify-start { justify-content: flex-start; }
        .items-center { align-items: center; }
        
        /* Spacing Utilities (simulating Tailwind) */
        .space-y-4 > *:not(:first-child) { margin-top: 1rem; }
        .gap-2 > *:not(:first-child) { margin-left: 0.5rem; }
        
        /* Overflow Utility */
        .overflow-y-auto { overflow-y: auto; }
        
        /* Spinner Animation */
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        /* Rounded Corners for Bubbles */
        .rounded-br-none { border-bottom-right-radius: 0 !important; }
        .rounded-bl-none { border-bottom-left-radius: 0 !important; }

        /* General button hover/focus styles (since inline styles don't support :hover/:focus) */
        button:hover:not(:disabled) {
            background-color: #4338CA; /* Darker indigo on hover */
        }
        button:focus:not(:disabled) {
            outline: none;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.5); /* Indigo ring on focus */
        }
        input:focus {
            outline: none;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.5); /* Indigo ring on focus */
            border-color: #6366F1; /* Indigo border on focus */
        }
        `}
      </style>

      {/* Chat Header */}
      <div style={chatHeaderStyle}>
        <h1 style={chatTitleStyle}>MANO-AI</h1>
        <button
          onClick={() => setCurrentView(currentView === 'chat' ? 'about' : 'chat')}
          style={aboutButtonStyle}
        >
          {currentView === 'chat' ? 'About' : 'Back to Chat'}
        </button>
      </div>

      {/* Conditional Rendering based on currentView */}
      {currentView === 'chat' ? (
        <>
          {/* Chat Messages Area */}
          <div style={messagesAreaStyle} className="space-y-4">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  style={msg.role === 'user' ? userMessageBubbleStyle : botMessageBubbleStyle}
                >
                  {/* Always render the general AI message content (introductory text) */}
                  <div dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>') }}></div>
                  
                  {/* Conditionally render structured recommendations if available */}
                  {msg.recommendations && msg.recommendations.length > 0 && renderRecommendations(msg.recommendations)}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div style={botMessageBubbleStyle}>
                  <div className="animate-spin" style={spinnerStyle}>
                    {/* Simple SVG spinner */}
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 4.75V6.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M17.1266 6.87347L16.0659 7.93414" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M19.25 12L17.75 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M17.1266 17.1265L16.0659 16.0659" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M12 17.75V19.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M7.93414 16.0659L6.87347 17.1266" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M4.75 12L6.25 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                      <path d="M7.93414 7.93414L6.87347 6.87347" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"></path>
                    </svg>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} /> {/* Scroll target */}
          </div>

          {/* Chat Input */}
          <div style={chatInputAreaStyle} className="gap-2">
            <input
              type="text"
              style={inputStyle}
              placeholder={mediaType ? `Type your ${mediaType} preference...` : "Type 'movie' or 'tv' to start..."}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !isLoading) {
                  handleSendMessage();
                }
              }}
              disabled={isLoading}
            />
            <button
              style={buttonStyle(isLoading)}
              onClick={handleSendMessage}
              disabled={isLoading}
            >
              Send
            </button>
          </div>
        </>
      ) : (
        <div style={aboutPageStyle}>
          <h2 style={aboutTitleStyle}>About MANO-AI</h2>
          <p style={aboutParagraphStyle}>
            This is your personal Movie and TV Show Recommendation Assistant.
            It helps you discover new content tailored to your unique preferences.
            Simply tell me what you're in the mood for – including genres, moods,
            styles, release years, and even specific languages or industries like
            Bollywood or Japanese anime – and I'll suggest the best matches for you.
            My recommendations are powered by a smart AI that processes your requests
            and identifies popular and highly-rated content to give you the best options.
          </p>
          <p style={aboutParagraphStyle}>
            Enjoy finding your next favorite movie or TV show!
          </p>
        </div>
      )}
    </div>
  );
}

// --- Inline Styles Definitions ---
// These styles are directly applied to JSX elements.
// Note: Some complex CSS features like :hover, :focus, or pseudo-elements
// cannot be directly applied via inline styles and are handled in the <style> tag.
const chatContainerStyle = {
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  backgroundColor: '#111827', // Dark background
  color: '#F9FAFB', // Light text
  borderRadius: '0.75rem', // More rounded corners
  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)', // Stronger shadow
  overflow: 'hidden',
  fontFamily: 'Inter, sans-serif', // Using Inter font
};

const chatHeaderStyle = {
  padding: '1rem',
  backgroundColor: '#1F2937', // Slightly lighter dark for header
  borderBottom: '1px solid #374151',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
};

const chatTitleStyle = {
  fontSize: '1.5rem', // Larger title
  fontWeight: 'bold',
  color: '#818CF8', // Indigo color for branding
};

const spinnerStyle = {
  height: '1.25rem',
  width: '1.25rem',
  color: '#818CF8',
};

const messagesAreaStyle = {
  flex: '1',
  padding: '1rem',
  overflowY: 'auto',
  backgroundColor: '#1F2937', // Match header background for continuity
};

const messageBubbleBaseStyle = {
  maxWidth: '70%',
  padding: '0.75rem',
  borderRadius: '0.5rem',
  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
};

const userMessageBubbleStyle = {
  ...messageBubbleBaseStyle,
  backgroundColor: '#4F46E5', // Indigo for user messages
  color: '#FFFFFF',
  borderBottomRightRadius: 0,
};

const botMessageBubbleStyle = {
  ...messageBubbleBaseStyle,
  backgroundColor: '#374151', // Darker gray for bot messages
  color: '#E5E7EB',
  borderBottomLeftRadius: 0,
};

const chatInputAreaStyle = {
  padding: '1rem',
  backgroundColor: '#1F2937',
  borderTop: '1px solid #374151',
  display: 'flex',
  alignItems: 'center',
};

const inputStyle = {
  flex: '1',
  padding: '0.75rem',
  borderRadius: '0.5rem',
  backgroundColor: '#374151',
  color: '#FFFFFF',
  border: '1px solid #4B5563', // Subtle border
  outline: 'none',
  boxSizing: 'border-box',
  // Placeholder color is handled by browser defaults or can be set via internal CSS
};

const buttonStyle = (isLoading) => ({
  backgroundColor: '#6366F1', // Indigo for buttons
  color: '#FFFFFF',
  padding: '0.75rem 1rem',
  borderRadius: '0.5rem',
  fontWeight: '600',
  transition: 'background-color 0.2s ease-in-out',
  outline: 'none',
  border: 'none',
  cursor: isLoading ? 'not-allowed' : 'pointer',
  opacity: isLoading ? 0.6 : 1, // Slightly more visible disabled state
});

const aboutButtonStyle = {
    backgroundColor: '#6366F1', // Indigo-500
    color: 'white',
    padding: '0.5rem 1rem',
    borderRadius: '0.375rem', // rounded-md
    fontWeight: 'semibold',
    cursor: 'pointer',
    border: 'none',
    transition: 'background-color 0.2s ease-in-out',
};

const aboutPageStyle = {
    flex: '1',
    padding: '2rem',
    overflowY: 'auto',
    backgroundColor: '#1F2937', // Dark background for about page
    color: '#E5E7EB', // Light text
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    textAlign: 'center',
};

const aboutTitleStyle = {
    fontSize: '1.75rem', // text-2xl
    fontWeight: 'bold',
    color: '#818CF8', // Indigo color
    marginBottom: '1rem',
};

const aboutParagraphStyle = {
    fontSize: '1rem', // text-base
    lineHeight: '1.6', // Improved line height for readability
    marginBottom: '1rem',
    maxWidth: '600px', // Constrain width for readability
    color: '#CBD5E0', // Slightly lighter gray for body text
};

// --- New styles for structured recommendations ---
const recommendationsContainerStyle = {
  marginTop: '1rem',
  paddingTop: '0.75rem',
  borderTop: '1px solid rgba(255, 255, 255, 0.1)', // Subtle separator
};

const recommendationsTitleStyle = {
  fontSize: '1.1rem',
  fontWeight: 'bold',
  marginBottom: '0.5rem',
  color: '#818CF8', // Indigo for titles
};

const recommendationsListStyle = {
  listStyle: 'none', // Remove default bullet points
  padding: 0,
  margin: 0,
};

const recommendationItemStyle = {
  marginBottom: '0.75rem',
  padding: '0.5rem',
  backgroundColor: '#2D3748', // Slightly lighter background for each item
  borderRadius: '0.375rem',
  boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
};

const recommendationTitleStyle = {
  color: '#E5E7EB', // Light text for title
  display: 'block', // Ensure title is on its own line
  marginBottom: '0.25rem',
};

const recommendationDescriptionStyle = {
  fontSize: '0.9rem',
  color: '#A0AEC0', // Lighter gray for description
  lineHeight: '1.4',
};

