// src/components/SearchBar.js
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/axiosinstance";
import Modal from "./Modal";

const formatReadableDateTime = (dateString) => {
  try {
    const date = new Date(dateString.split(".")[0].replace(" ", "T") + "Z");

    if (isNaN(date.getTime())) {
      console.warn("Could not parse date:", dateString);
      return dateString;
    }

    const options = {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    };
    return new Intl.DateTimeFormat("en-US", options).format(date);
  } catch (error) {
    console.error("Error formatting date:", error);
    return dateString;
  }
};

const SearchBar = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalContent, setModalContent] = useState({
    message: "",
    existingAnalysis: null,
    ticker: null,
  });
  const [isGenerating, setIsGenerating] = useState(false);

  const navigate = useNavigate();
  const searchContainerRef = useRef(null);

  useEffect(() => {
    if (!searchTerm.trim()) {
      setResults([]);
      setShowResults(false);
      return;
    }
    setIsLoading(true);
    setShowResults(true);
    const delayDebounceFn = setTimeout(async () => {
      try {
        const response = await apiClient.get("/stock-query", {
          params: { q: searchTerm },
        });
        setResults(response.data || []);
      } catch (error) {
        console.error("Failed to fetch stock suggestions:", error);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);
    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target)
      ) {
        setShowResults(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleInputChange = (event) => {
    setSearchTerm(event.target.value);
  };

  const handleResultClick = useCallback(
    async (ticker) => {
      setSearchTerm("");
      setResults([]);
      setShowResults(false);
      try {
        console.log(`Checking analysis for ticker: ${ticker}`);
        const response = await apiClient.get("/check-analysis", {
          params: { ticker },
        });
        const responseData = response.data;
        console.log("Response from /check-analysis:", responseData);

        let displayMessage = responseData.message;

        if (
          responseData.existing_analysis &&
          typeof displayMessage === "string"
        ) {
          const dateTimeRegex =
            /(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(\.\d+)?)/;
          const match = displayMessage.match(dateTimeRegex);

          if (match && match[1]) {
            const originalDateTimeString = match[1];
            const formattedDateTime = formatReadableDateTime(
              originalDateTimeString
            );
            if (formattedDateTime !== originalDateTimeString) {
              displayMessage = displayMessage.replace(
                originalDateTimeString,
                formattedDateTime
              );
            }
          }
        }

        setModalContent({
          message: displayMessage,
          existingAnalysis: responseData.existing_analysis,
          ticker: ticker,
        });
        setIsModalOpen(true);
      } catch (error) {
        console.error(`Failed to check analysis for ${ticker}:`, error);
        const errorMsg =
          error.response?.data?.message ||
          `Error checking analysis for ${ticker}. Please try again.`;
        setModalContent({
          message: errorMsg,
          existingAnalysis: null,
          ticker: null,
        });
        setIsModalOpen(true);
      }
    },
    [navigate]
  );

  const closeModal = () => {
    setIsModalOpen(false);
    if (isGenerating) {
      setIsGenerating(false);
    }
  };

  const handleGenerateAnalysis = async () => {
    const currentTicker = modalContent.ticker;
    if (!currentTicker) return;

    setIsGenerating(true);

    try {
      console.log(`Generating analysis for ticker: ${currentTicker}`);
      const response = await apiClient.get("/generate-analysis", {
        params: { ticker: currentTicker },
      });
      const data = response.data;
      console.log("Response from /generate-analysis:", data);

      if (data.status === "started" && data.task_id) {
        console.log(`Navigating to loading page for task ${data.task_id}`);
        navigate(`/loading-analysis/${data.task_id}/${currentTicker}`);
        return;
      } else {
        console.error("Analysis task did not start as expected:", data);
        setModalContent((prev) => ({
          ...prev,
          message:
            data.message || "Failed to start analysis task. Please try again.",
        }));
        setIsGenerating(false);
      }
    } catch (error) {
      console.error(`Failed to generate analysis for ${currentTicker}:`, error);
      const errorMsg =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        "An error occurred while starting the analysis.";
      setModalContent((prev) => ({
        ...prev,
        message: errorMsg,
      }));
      setIsGenerating(false);
    }
  };

  const handleAccessExisting = () => {
    if (modalContent.ticker) {
      navigate(`/stock/${modalContent.ticker}`);
      closeModal();
    }
  };

  return (
    <div className="relative w-full" ref={searchContainerRef}>
      {/* Search Input */}
      <div className="flex gap-3 items-center px-4 py-2.5 rounded-full border border-gray-700 bg-dark-background text-light-text min-h-12 w-full focus-within:border-green-500">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="size-6"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
          />
        </svg>

        <input
          type="text"
          value={searchTerm}
          onChange={handleInputChange}
          onFocus={() => searchTerm.trim() && setShowResults(true)}
          placeholder="Search Stocks (e.g., AAPL, GOOG)..."
          className="w-full bg-transparent outline-none border-none text-light-text placeholder-gray-400"
        />
      </div>

      {/* Results Dropdown */}
      {showResults && (
        <div className="absolute top-full left-0 right-0 mt-1.5 bg-dark-background border border-gray-700 rounded-2xl shadow-lg z-10 max-h-60 overflow-y-auto">
          {isLoading && <div className="p-3 text-gray-400">Loading...</div>}
          {!isLoading && results.length === 0 && searchTerm.trim() && (
            <div className="p-3 text-gray-400">No results found.</div>
          )}
          {!isLoading &&
            results.map((result, index) => (
              <div
                key={result.ticker}
                onClick={() => handleResultClick(result.ticker)}
                className={`p-3 hover:bg-gray-700 cursor-pointer text-light-text flex justify-between items-center
                           ${index === 0 ? "rounded-t-2xl" : ""}
                           ${
                             index === results.length - 1 ? "rounded-b-2xl" : ""
                           }`}
              >
                <span className="font-medium">{result.ticker}</span>
                <span className="text-sm text-gray-400 truncate ml-2">
                  {result.title}
                </span>
              </div>
            ))}
        </div>
      )}

      {/* Confirmation Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal} // Use the updated closeModal
        message={modalContent.message}
        existingAnalysis={modalContent.existingAnalysis}
        onYes={handleGenerateAnalysis} // Use the updated handler
        onNo={closeModal} // Directly close modal on "No"
        onAccessExisting={handleAccessExisting}
        onCreateNew={handleGenerateAnalysis} // Use the updated handler
        isGenerating={isGenerating}
      />
    </div>
  );
};

export default SearchBar;
