'use client';

import { useState, useRef, useEffect, ChangeEvent } from 'react';
import { useParams } from 'next/navigation';
import { Container, Dialog, DialogTitle, DialogContent } from '@mui/material';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2 } from 'lucide-react';
import { useKnowledgeExtractionEndpoints, Question, Report, QuestionResult } from '@/lib/backend';

interface ResultsViewProps {
  report: Report;
  onClose: () => void;
}

interface QuestionItemProps {
  question: Question;
  onEdit: (id: string, text: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

const ResultsView: React.FC<ResultsViewProps> = ({ report, onClose }) => {
  if (!report.content) return null;

  return (
    <div className="space-y-6 mt-4">
      {report.content.results.map((result: QuestionResult) => (
        <div
          key={result.question_id}
          className="border rounded-lg p-6 bg-white shadow-sm hover:shadow-md transition-shadow"
        >
          <h3 className="text-lg font-semibold mb-3">{result.question}</h3>
          <p className="text-gray-700 mb-4 leading-relaxed">{result.answer}</p>
          <div className="space-y-3">
            <h4 className="font-medium text-sm text-gray-600">References</h4>
            {result.references.map((ref, idx) => (
              <div key={idx} className="bg-gray-50 p-4 rounded-lg border border-gray-100">
                <p className="text-gray-700">{ref.text}</p>
                <p className="text-gray-500 text-sm mt-2">Source: {ref.source}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

const QuestionItem: React.FC<QuestionItemProps> = ({ question, onEdit, onDelete }) => {
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editText, setEditText] = useState<string>(question.question_text);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  return (
    <div className="group bg-white rounded-lg border p-4 hover:border-blue-200 transition-all">
      {isEditing ? (
        <div className="space-y-3">
          <Input
            ref={inputRef}
            value={editText}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setEditText(e.target.value)}
            className="w-full"
          />
          <div className="flex justify-end gap-2">
            <Button
              onClick={async () => {
                await onEdit(question.question_id, editText);
                setIsEditing(false);
              }}
              variant="default"
              size="sm"
            >
              Save
            </Button>
            <Button
              onClick={() => {
                setEditText(question.question_text);
                setIsEditing(false);
              }}
              variant="outline"
              size="sm"
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <p className="flex-grow">{question.question_text}</p>
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
            <Button onClick={() => setIsEditing(true)} variant="ghost" size="sm">
              Edit
            </Button>
            <Button onClick={() => onDelete(question.question_id)} variant="destructive" size="sm">
              Delete
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

const Page: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('reports');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [newQuestionText, setNewQuestionText] = useState<string>('');

  const params = useParams();
  const workflowId = params?.deploymentId as string;
  const {
    listReports,
    createReport,
    getReport,
    deleteReport,
    addQuestion,
    getQuestions,
    deleteQuestion,
    editQuestion,
  } = useKnowledgeExtractionEndpoints(workflowId);

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const [fetchedQuestions, fetchedReportStatuses] = await Promise.all([
          getQuestions(),
          listReports(),
        ]);
        setQuestions(fetchedQuestions);
        const reportDetails = await Promise.all(
          fetchedReportStatuses.map((r) => getReport(r.report_id))
        );
        setReports(reportDetails);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const getFileName = (path: string): string => path.split('/').pop() || path;

  const filteredReports = reports.filter((report: Report): boolean =>
    report.documents?.some((doc) =>
      getFileName(doc.path).toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  useEffect(() => {
    const incompleteReports = reports.filter(
      (report) => !['complete', 'failed'].includes(report.status)
    );

    if (incompleteReports.length === 0) return;

    // Create a map to store intervals
    const intervalMap: { [key: string]: number } = {};

    // Start polling for each incomplete report
    incompleteReports.forEach((report) => {
      intervalMap[report.report_id] = window.setInterval(async () => {
        try {
          const updatedReport = await getReport(report.report_id);
          setReports((prevReports) =>
            prevReports.map((r) => (r.report_id === report.report_id ? updatedReport : r))
          );

          if (['complete', 'failed'].includes(updatedReport.status)) {
            clearInterval(intervalMap[report.report_id]);
          }
        } catch (error) {
          console.error('Error polling report status:', error);
          clearInterval(intervalMap[report.report_id]);
        }
      }, 3000);
    });

    // Cleanup function to clear all intervals
    return () => {
      Object.values(intervalMap).forEach((interval) => clearInterval(interval));
    };
  }, [reports]);

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>): Promise<void> => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setIsLoading(true);
    try {
      const currentReports = [...reports];
      for (const file of files) {
        const reportId = await createReport([file]);
        const report = await getReport(reportId);
        currentReports.push(report);
        setReports([...currentReports]);
      }
    } catch (error) {
      console.error('Error uploading files:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuestionAdd = async (): Promise<void> => {
    if (!newQuestionText.trim()) return;
    try {
      await addQuestion(newQuestionText.trim());
      const updatedQuestions = await getQuestions();
      setQuestions(updatedQuestions);
      setNewQuestionText('');
    } catch (error) {
      console.error('Error adding question:', error);
    }
  };

  const handleQuestionEdit = async (id: string, text: string): Promise<void> => {
    try {
      await editQuestion(id, text);
      const updatedQuestions = await getQuestions();
      setQuestions(updatedQuestions);
    } catch (error) {
      console.error('Error editing question:', error);
    }
  };

  const handleQuestionDelete = async (id: string): Promise<void> => {
    try {
      await deleteQuestion(id);
      setQuestions(questions.filter((q) => q.question_id !== id));
    } catch (error) {
      console.error('Error deleting question:', error);
    }
  };

  const handleReportDelete = async (reportId: string): Promise<void> => {
    try {
      await deleteReport(reportId);
      setReports((prevReports) => prevReports.filter((r) => r.report_id !== reportId));
    } catch (error) {
      console.error('Error deleting report:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Container className="py-8 max-w-5xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Knowledge Extraction</h1>
          <p className="text-gray-600">Upload documents and manage extraction questions</p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-2 max-w-md">
            <TabsTrigger value="reports">Reports</TabsTrigger>
            <TabsTrigger value="questions">Questions</TabsTrigger>
          </TabsList>

          <TabsContent value="reports" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Documents</h2>
                  <Button onClick={() => fileInputRef.current?.click()} variant="default">
                    Upload New Document
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={handleFileUpload}
                    multiple
                  />
                </div>
                <Input
                  type="search"
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                  className="max-w-md"
                />
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    {filteredReports.map((report: Report) => (
                      <div key={report.report_id} className="space-y-3">
                        {report.documents.map((doc) => (
                          <div
                            key={doc.path}
                            className="flex items-center justify-between p-4 bg-white rounded-lg border hover:border-blue-200 transition-all"
                          >
                            <div className="flex flex-col">
                              <span className="font-medium">{getFileName(doc.path)}</span>
                              <span className="text-sm text-gray-500">
                                {new Date(report.submitted_at).toLocaleString()}
                              </span>
                            </div>
                            <div className="flex items-center gap-3">
                              <Badge
                                variant={report.status === 'complete' ? 'default' : 'secondary'}
                                className={
                                  report.status === 'complete'
                                    ? 'bg-green-100 text-green-800'
                                    : report.status === 'failed'
                                      ? 'bg-red-100 text-red-800'
                                      : 'bg-yellow-100 text-yellow-800'
                                }
                              >
                                {report.status}
                              </Badge>
                              {report.status === 'complete' && report.content && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setSelectedReport(report)}
                                >
                                  View Results
                                </Button>
                              )}
                              <Button
                                onClick={() => handleReportDelete(report.report_id)}
                                variant="destructive"
                                size="sm"
                              >
                                Delete
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="questions" className="space-y-6">
            <Card>
              <CardHeader>
                <h2 className="text-xl font-semibold">Manage Questions</h2>
                <div className="flex gap-2 max-w-2xl">
                  <Input
                    value={newQuestionText}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      setNewQuestionText(e.target.value)
                    }
                    placeholder="Enter new question..."
                    className="flex-grow"
                  />
                  <Button onClick={handleQuestionAdd} disabled={!newQuestionText.trim()}>
                    Add Question
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-w-2xl">
                  {questions.map((question: Question) => (
                    <QuestionItem
                      key={question.question_id}
                      question={question}
                      onEdit={handleQuestionEdit}
                      onDelete={handleQuestionDelete}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <Dialog
          open={!!selectedReport}
          onClose={() => setSelectedReport(null)}
          maxWidth="lg"
          fullWidth
        >
          <DialogTitle>
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">Report Results</h2>
              <Button onClick={() => setSelectedReport(null)} variant="ghost" size="sm">
                Close
              </Button>
            </div>
          </DialogTitle>
          <DialogContent>
            {selectedReport && (
              <ResultsView report={selectedReport} onClose={() => setSelectedReport(null)} />
            )}
          </DialogContent>
        </Dialog>
      </Container>
    </div>
  );
};

export default Page;
