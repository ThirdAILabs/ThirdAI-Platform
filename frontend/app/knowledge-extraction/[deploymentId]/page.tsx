'use client';

import { useState, useRef, useEffect, ChangeEvent } from 'react';
import { useParams } from 'next/navigation';
import { Container } from '@mui/material';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardHeader } from '@/components/ui/card';
import { useKnowledgeExtractionEndpoints } from '@/lib/backend';

interface Question {
  id: string;
  text: string;
  keywords?: string[];
}

interface Report {
  id: string;
  name: string;
  content: string;
}

export default function Page(): JSX.Element {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showQuestions, setShowQuestions] = useState<boolean>(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const params = useParams();
  const workflowId = params?.deploymentId as string;

  const {
    createReport,
    getReport,
    deleteReport,
    addQuestion,
    getQuestions,
    deleteQuestion,
    editQuestion,
  } = useKnowledgeExtractionEndpoints(workflowId);

  useEffect(() => {
    const fetchQuestions = async () => {
      const fetchedQuestions = await getQuestions();
      setQuestions(fetchedQuestions);
    };
    fetchQuestions();
  }, []);

  const filteredReports = reports.filter((report: Report): boolean =>
    report.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      try {
        const reportId = await createReport(files);
        const report = await getReport(reportId);
        setReports([...reports, report]);
      } catch (error) {
        console.error('Error uploading file:', error);
      }
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    try {
      await deleteReport(reportId);
      setReports(reports.filter((r) => r.id !== reportId));
    } catch (error) {
      console.error('Error deleting report:', error);
    }
  };

  const handleAddQuestion = async () => {
    try {
      const questionId = await addQuestion('New Question');
      const updatedQuestions = await getQuestions();
      setQuestions(updatedQuestions);
    } catch (error) {
      console.error('Error adding question:', error);
    }
  };

  const handleEditQuestion = async (questionId: string, newText: string) => {
    try {
      await editQuestion(questionId, newText);
      const updatedQuestions = await getQuestions();
      setQuestions(updatedQuestions);
    } catch (error) {
      console.error('Error editing question:', error);
    }
  };

  const handleDeleteQuestion = async (questionId: string) => {
    try {
      await deleteQuestion(questionId);
      setQuestions(questions.filter((q) => q.id !== questionId));
    } catch (error) {
      console.error('Error deleting question:', error);
    }
  };

  return (
    <div className="bg-muted min-h-screen">
      <div className="fixed top-6 right-6">
        <Button onClick={() => setShowQuestions(!showQuestions)} className="bg-blue-500 text-white">
          Edit Questions
        </Button>
      </div>

      {!showQuestions ? (
        <Container className="pt-20 max-w-4xl">
          <Card className="bg-white p-6">
            <CardHeader>
              <h2 className="text-2xl font-bold mb-4">Select Document</h2>
              <Input
                type="search"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                className="mb-4"
              />
            </CardHeader>
            <div className="space-y-2">
              <Button
                onClick={() => fileInputRef.current?.click()}
                className="w-full text-left p-4 hover:bg-gray-50"
              >
                + Add new file
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileUpload}
                multiple
              />
              {filteredReports.map((report: Report) => (
                <div
                  key={report.id}
                  className="flex items-center justify-between p-4 hover:bg-gray-50"
                >
                  <span>{report.name}</span>
                  <Button
                    onClick={() => handleDeleteReport(report.id)}
                    variant="destructive"
                    size="sm"
                  >
                    Delete
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        </Container>
      ) : (
        <Container className="pt-20 max-w-4xl">
          <Card className="bg-white p-6">
            <CardHeader>
              <h2 className="text-2xl font-bold mb-4">Edit Questions</h2>
            </CardHeader>
            <div className="space-y-4">
              {questions.map((question: Question) => (
                <div key={question.id} className="flex items-center gap-2">
                  <Input
                    value={question.text}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      handleEditQuestion(question.id, e.target.value)
                    }
                    className="flex-grow"
                  />
                  <Button onClick={() => handleDeleteQuestion(question.id)} variant="destructive">
                    Delete
                  </Button>
                </div>
              ))}
              <Button onClick={handleAddQuestion} className="w-full mt-4">
                Ask New Question
              </Button>
            </div>
          </Card>
        </Container>
      )}
    </div>
  );
}
