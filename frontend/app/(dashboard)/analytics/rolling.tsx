import { useEffect, useState } from 'react';

export default function useRollingSamples<T>(
  samples: T[],
  numSamples: number,
  numNewSamples: number,
): (T & { timestamp: string })[] {
  const randomSamples = (sampleSize: number): T[] => {
    const result: T[] = [];
    while (result.length < sampleSize) {
      const randomIndex = Math.floor(Math.random() * samples.length);
      result.push(samples[randomIndex]);
    }
    return result;
  };

  const aLittleBeforeNow = (regress: number): string => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - regress);

    const day = now.getDate();
    const month = now.toLocaleString('en-US', { month: 'long' });
    const year = now.getFullYear();

    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    const seconds = now.getSeconds().toString().padStart(2, '0');

    return `${day} ${month} ${year} ${hours}:${minutes}:${seconds}`;
  };

  const addTimes = (
    samples: T[],
    maxRegressSeconds: number
  ): (T & { timestamp: string })[] => {
    const regresses = samples.map(() =>
      Math.floor(Math.random() * (maxRegressSeconds + 1))
    );
    regresses.sort();
    return samples.map((sample, idx) => ({
      ...sample,
      timestamp: aLittleBeforeNow(regresses[idx])
    }));
  };

  const rollSamples = () => {
    setRollingSamples((prev) =>
      [
        ...addTimes(randomSamples(numNewSamples), 1),
        ...prev
      ].slice(0, numSamples)
    );
  };

  const [rollingSamples, setRollingSamples] = useState<
    (T & { timestamp: string })[]
  >(addTimes(randomSamples(numSamples), 10));

  useEffect(() => {
    const intervalId = setInterval(rollSamples, 2000);

    // Cleanup function to clear the interval when the component unmounts
    return () => clearInterval(intervalId);
  }, []);

  return rollingSamples;
}
