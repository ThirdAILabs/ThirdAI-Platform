import React, { useState, useEffect } from 'react';
import { getAllChatHistory } from '@/lib/backend';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button, Divider } from '@mui/material';
interface ConversationData {
  query_time: string;
  query_text: string;
  user_input: string;
  response_time: string;
  response_text: string;
  user_input_category: string;
}

interface Data {
  [sessionId: string]: ConversationData[]; // Maps session IDs to an array of conversations
}
function min(a: number, b: number) {
  if (a < b) return a;
  return b;
}
function getUrlParams() {
  const url = new URL(window.location.href);
  const params = new URLSearchParams(url.search);
  const userName = params.get('username');
  const modelName = params.get('model_name');
  const model_id = params.get('old_model_id');
  const default_mode = params.get('default');
  return { userName, modelName, model_id, default_mode };
}
function convertAndSortDataByQueryTime(data: Data): ConversationData[] {
  const conversationList: ConversationData[] = [];
  for (const [sessionId, conversations] of Object.entries(data)) {
    conversations.forEach((conversation) => {
      conversationList.push({ ...conversation });
    });
  }
  // Sort the list by query_time
  conversationList.sort(
    (a, b) => new Date(b.query_time).getTime() - new Date(a.query_time).getTime()
  );
  return conversationList;
}

function getUniqueCategories(chatHistory: ConversationData[]): string[] {
  const uniqueCategories = new Set<string>();
  for (const conversation of chatHistory) {
    uniqueCategories.add(conversation.user_input_category);
  }
  return Array.from(uniqueCategories);
}

const Conversations: React.FC = () => {
  // State variable for storing chat history
  const [chatHistory, setChatHistory] = useState<ConversationData[]>([]);
  const [numberOfQuestions, setNumberOfQuestions] = useState<number>(0);
  const [categoryList, setCategoryList] = useState<string[]>([]);
  const handleShowMore = () => {
    setNumberOfQuestions(min(numberOfQuestions + 50, chatHistory.length));
  };

  // Extract parameters from the URL
  const { model_id, default_mode } = getUrlParams();
  useEffect(() => {
    if (default_mode === 'chat' && model_id !== null) {
      const getChatData = async () => {
        try {
          const data = await getAllChatHistory(model_id);
          const convertedData = convertAndSortDataByQueryTime(data);
          setChatHistory(convertedData);
          setNumberOfQuestions(min(50, convertedData.length));
          setCategoryList(getUniqueCategories(convertedData));
        } catch (error) {
          console.error('Error fetching chat history:', error);
        }
      };
      getChatData();
    }
  }, [model_id, default_mode]);

  if (!chatHistory) {
    return <div className="p-4 text-center">Loading chat history...</div>;
  }

  const [selectedCategories, setSelectedCategories] = useState(
    Object.fromEntries(categoryList.map((category) => [category, false]))
  );

  // Toggle handler for category selection
  const handleCategoryToggle = (category: string) => {
    setSelectedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  // Get list of currently selected categories
  const getSelectedCategories = () => {
    return Object.entries(selectedCategories)
      .filter(([_, isSelected]) => isSelected)
      .map(([category]) => category);
  };

  return (
    <div className="p-4">
      <Card style={{ width: '70%', maxHeight: '65rem' }} className="pb-4">
        <CardHeader className="bg-blue-900 text-white mb-3">
          <CardTitle>Query Archive</CardTitle>
          <CardDescription className="text-white">
            Quick access to your asked questions
          </CardDescription>
        </CardHeader>
        <CardContent style={{ overflowY: 'auto', maxHeight: '45rem' }}>
          <>
            <div className="mb-2 justify-start ml-[5%] mr-[5%]">
              <div className="space-y-4 mb-2">
                <div className="flex flex-wrap gap-2">
                  {categoryList.map((category, index) => (
                    <button
                      key={`${category}-${index}`}
                      onClick={() => handleCategoryToggle(category)}
                      className={`border rounded-xl p-1 px-4 transition-colors
              ${
                selectedCategories[category]
                  ? 'bg-blue-900 text-white'
                  : 'hover:bg-slate-100 hover:text-black'
              }`}
                    >
                      {category}
                    </button>
                  ))}
                </div>

                <div className="text-sm text-gray-600">
                  Selected categories: {getSelectedCategories().join(', ') || 'None'}
                </div>
              </div>
              <Divider />
            </div>
            {chatHistory.map((conversation, index) => {
              return (
                index < numberOfQuestions && (
                  <div
                    key={`${conversation.query_time}-${conversation.response_time}`}
                    className="mb-1"
                  >
                    <div className="flex flex-col">
                      {/* Query Section */}
                      <div className="flex justify-center">
                        {(selectedCategories[conversation.user_input_category] === true ||
                          !getSelectedCategories().join(', ')) && (
                          <div className="border py-2 px-4 rounded-lg w-[90%]">
                            <div className="text-gray-700 flex flex-wrap">
                              {' '}
                              <strong>User Query: </strong>
                              {' ' + conversation.user_input}
                            </div>
                            <div className="text-gray-700">
                              <strong>Reformulated Query:</strong>
                              {' ' + conversation.query_text}
                            </div>
                            <div className="text-xs text-gray-500">{conversation.query_time}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              );
            })}
            {numberOfQuestions < chatHistory.length && (
              <div className="flex justify-center mt-2">
                <Button variant="contained" onClick={handleShowMore}>
                  Show More
                </Button>
              </div>
            )}
          </>
        </CardContent>
      </Card>
    </div>
  );
};

export default Conversations;
